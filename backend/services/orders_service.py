import re
from datetime import date

from pymongo import ReturnDocument

from backend.db.mongo import get_client, get_db, next_sequence
from backend.models.schemas import (
    validate_fields, ORDER_UPDATE_SPEC, ValidationError,
    ORDER_STATUS_FLOW, ORDER_CANCELLABLE_FROM,
)
from backend.services.common import serialize, serialize_many
from backend.services.customers_service import find_or_create_customer

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INITIAL_ORDER_STATUS = ORDER_STATUS_FLOW[0]  # "ממתין לאישור" — new orders always start here
_PENDING_PAYMENT = "ממתין לתשלום"  # no real payment processing exists yet (Phase 1)


def _validate_transition(current_status, new_status):
    if new_status == current_status:
        return
    if new_status == "בוטל":
        if current_status not in ORDER_CANCELLABLE_FROM:
            raise ValidationError(
                f"לא ניתן לבטל הזמנה שנמצאת בסטטוס '{current_status}'"
            )
        return
    if current_status == "בוטל" or current_status == "נמסר":
        raise ValidationError(f"לא ניתן לשנות סטטוס של הזמנה שכבר '{current_status}'")
    if new_status not in ORDER_STATUS_FLOW:
        raise ValidationError(f"סטטוס לא תקין: '{new_status}'")
    current_idx = ORDER_STATUS_FLOW.index(current_status) if current_status in ORDER_STATUS_FLOW else -1
    new_idx = ORDER_STATUS_FLOW.index(new_status)
    if new_idx != current_idx + 1:
        raise ValidationError(
            f"מעבר סטטוס לא חוקי: '{current_status}' -> '{new_status}'. "
            f"הסדר החוקי הוא: {' -> '.join(ORDER_STATUS_FLOW)}"
        )


def list_orders(filters=None):
    db = get_db()
    query = {}
    if filters:
        if filters.get("status"):
            query["status"] = filters["status"]
        if filters.get("customerId"):
            query["customerId"] = filters["customerId"]
    docs = db.orders.find(query).sort("date", -1)
    return serialize_many(docs)


def get_order(order_id):
    db = get_db()
    return serialize(db.orders.find_one({"_id": order_id}))


def update_order(order_id, patch):
    validate_fields(patch, ORDER_UPDATE_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("id", "_id")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    db = get_db()

    if "status" in patch:
        current = db.orders.find_one({"_id": order_id}, {"status": 1})
        if not current:
            return None
        _validate_transition(current["status"], patch["status"])

    result = db.orders.find_one_and_update(
        {"_id": order_id},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return serialize(result)


# =====================================================================
# Real checkout: customer order -> MongoDB -> inventory update.
# =====================================================================

def _validate_checkout_payload(data):
    """Structural validation of the checkout request. Business-rule
    checks that need a database read (does the product exist? is there
    enough stock?) happen later, inside create_order's transaction, where
    a definitive answer is possible."""
    if not isinstance(data, dict):
        raise ValidationError("גוף הבקשה חייב להיות אובייקט JSON")

    customer = data.get("customer")
    if not isinstance(customer, dict):
        raise ValidationError("נתוני לקוח חסרים")
    name = (customer.get("name") or "").strip()
    email = (customer.get("email") or "").strip()
    phone = (customer.get("phone") or "").strip()
    if not name:
        raise ValidationError("שם הלקוח הוא שדה חובה")
    if not email or not _EMAIL_RE.match(email):
        raise ValidationError("כתובת דוא\"ל אינה תקינה")
    if not phone:
        raise ValidationError("מספר טלפון הוא שדה חובה")

    shipping = data.get("shipping")
    if not isinstance(shipping, dict):
        raise ValidationError("נתוני משלוח חסרים")
    address = (shipping.get("address") or "").strip()
    city = (shipping.get("city") or "").strip()
    if not address:
        raise ValidationError("כתובת למשלוח היא שדה חובה")
    if not city:
        raise ValidationError("עיר למשלוח היא שדה חובה")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValidationError("ההזמנה חייבת לכלול לפחות פריט אחד")
    clean_items = []
    for it in items:
        if not isinstance(it, dict):
            raise ValidationError("פריט הזמנה לא תקין")
        pid = it.get("productId")
        qty = it.get("qty")
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise ValidationError("מזהה מוצר לא תקין")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise ValidationError("כמות הפריטים חייבת להיות מספר שלם חיובי")
        clean_items.append({"productId": pid, "qty": qty})

    payment = data.get("payment")
    if not isinstance(payment, dict) or not (payment.get("method") or "").strip():
        raise ValidationError("אמצעי תשלום הוא שדה חובה")

    return {
        "customer": {"name": name, "email": email, "phone": phone},
        "shipping": {
            "method": (shipping.get("method") or "").strip() or "משלוח סטנדרטי",
            "address": address,
            "city": city,
            "zip": (shipping.get("zip") or "").strip(),
            "notes": (shipping.get("notes") or "").strip(),
        },
        "items": clean_items,
        "payment": {"method": payment["method"].strip()},
    }


def create_order(payload):
    """The real checkout pipeline: validate -> look up/create the customer
    -> atomically validate & decrement stock for every item -> compute
    shipping from store-info -> write the order. Product price/stock/name/
    sku are always read fresh from MongoDB; whatever the client sent for
    those is ignored.

    Stock checks + decrements + the order write happen inside a single
    MongoDB transaction (this deployment's replica set supports them), so
    a failure partway through — insufficient stock on item 3 of 4, a
    write error, anything — leaves no partial order and no partial stock
    change behind; the transaction aborts as a whole.
    """
    clean = _validate_checkout_payload(payload)
    db = get_db()
    client = get_client()

    # Customer lookup/creation is intentionally outside the transaction —
    # see find_or_create_customer's docstring for why.
    customer = find_or_create_customer(
        clean["customer"]["name"], clean["customer"]["email"], clean["customer"]["phone"]
    )

    with client.start_session() as session:
        with session.start_transaction():
            line_items = []
            subtotal = 0

            for item in clean["items"]:
                pid, qty = item["productId"], item["qty"]
                product = db.products.find_one({"_id": pid}, session=session)
                if not product:
                    raise ValidationError(f"מוצר עם מזהה {pid} אינו קיים")
                if product.get("status") == "draft":
                    raise ValidationError(f"המוצר '{product['name']}' אינו זמין לרכישה כרגע")
                current_stock = product.get("stock", 0)
                if current_stock < qty:
                    raise ValidationError(
                        f"המוצר '{product['name']}' אינו זמין במלאי בכמות המבוקשת. "
                        f"המלאי הזמין הוא {current_stock}."
                    )

                # Atomic, condition-guarded decrement: the {"stock": {"$gte": qty}}
                # filter means this only succeeds if the stock is still
                # sufficient AT THE MOMENT OF THE WRITE, closing the race
                # window between the check above and this update. The
                # pipeline form lets `status` flip to "out" based on the
                # POST-decrement stock in the same atomic operation.
                updated = db.products.find_one_and_update(
                    {"_id": pid, "stock": {"$gte": qty}},
                    [
                        {"$set": {
                            "stock": {"$subtract": ["$stock", qty]},
                            "sold": {"$add": [{"$ifNull": ["$sold", 0]}, qty]},
                        }},
                        {"$set": {
                            "status": {"$cond": [{"$lte": ["$stock", 0]}, "out", "$status"]},
                        }},
                    ],
                    session=session,
                    return_document=ReturnDocument.AFTER,
                )
                if not updated:
                    # A concurrent order consumed the remaining stock between
                    # the read above and this write — abort cleanly.
                    raise ValidationError(
                        f"המוצר '{product['name']}' אינו זמין במלאי בכמות המבוקשת כרגע"
                    )

                line_total = product["price"] * qty
                subtotal += line_total
                line_items.append({
                    "productId": pid,
                    "name": product["name"],
                    "sku": product.get("sku", ""),
                    "cat": product.get("catLabel", ""),
                    "price": product["price"],
                    "qty": qty,
                    "lineTotal": line_total,
                })

            store_info = db.store_info.find_one({"_id": "store_info"}, session=session) or {}
            ship_cost = store_info.get("shippingCost", 0)
            free_threshold = store_info.get("freeShippingThreshold")
            shipping_cost = 0 if (free_threshold is not None and subtotal >= free_threshold) else ship_cost
            grand_total = subtotal + shipping_cost

            order_id = f"BJ-{next_sequence(db, 'order_id', session=session)}"
            today = date.today().isoformat()

            order_doc = {
                "_id": order_id,
                "customerId": customer["_id"],
                "customer": {
                    "id": customer["_id"],
                    "name": clean["customer"]["name"],
                    "email": clean["customer"]["email"].lower(),
                    "phone": clean["customer"]["phone"],
                },
                "date": today,
                "items": line_items,
                "total": subtotal,          # historical convention: "total" = items subtotal (see shared/models.js)
                "shippingCost": shipping_cost,
                "grandTotal": grand_total,
                "status": _INITIAL_ORDER_STATUS,
                "pay": _PENDING_PAYMENT,
                "shipping": clean["shipping"],
                "payment": {"method": clean["payment"]["method"], "date": today},
            }
            db.orders.insert_one(order_doc, session=session)

            db.customers.update_one(
                {"_id": customer["_id"]},
                {"$inc": {"orders": 1, "spent": subtotal}},
                session=session,
            )

    return {
        "id": order_id,
        "customerId": customer["_id"],
        "subtotal": subtotal,
        "shipping": shipping_cost,
        "total": grand_total,
        "status": _INITIAL_ORDER_STATUS,
    }
