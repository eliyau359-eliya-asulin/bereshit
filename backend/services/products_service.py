"""
Products are stored with MongoDB's `_id` set to the same numeric id the
frontend already used (shared/mock-data.js, admin/js/data.js) — so a
product id is identical across Admin, the API, MongoDB, and the customer
site, exactly as requested: PUT /api/products/123 updates _id=123.

Inventory is a single number: `stock` is the one real source of truth
for physical units on hand, decremented by real online orders
(orders_service.create_order) and by admin-recorded adjustments here —
never a separate onlineStock/physicalStock split. `status` is a
distinct concept (is the product allowed to sell online at all) that
stays in sync with stock automatically (0 -> "out", restocked -> back
to "active") but is never conflated with the stock number itself: a
"draft" product keeps its own status regardless of stock.
"""
from datetime import datetime, timezone

from pymongo import ReturnDocument

from backend.db.mongo import get_db
from backend.models.schemas import validate_fields, PRODUCT_SPEC, ValidationError
from backend.services.common import serialize, serialize_many


def list_products(filters=None):
    db = get_db()
    query = {}
    if filters:
        if filters.get("cat"):
            query["cat"] = filters["cat"]
        if filters.get("status"):
            query["status"] = filters["status"]
    docs = db.products.find(query).sort("_id", 1)
    return serialize_many(docs)


def get_product(product_id):
    db = get_db()
    return serialize(db.products.find_one({"_id": product_id}))


def find_by_code(code):
    """Used by the admin barcode scanner: matches a scanned/typed barcode
    first (the real-world identifier printed on the item), falling back to
    SKU (useful for manual entry when a barcode is missing/unreadable) —
    the same product data either way, resolved through the one real
    products collection, never a separate lookup table."""
    db = get_db()
    code = (code or "").strip()
    if not code:
        return None
    doc = db.products.find_one({"barcode": code})
    if not doc:
        doc = db.products.find_one({"sku": code})
    return serialize(doc)


def create_product(data):
    validate_fields(data, PRODUCT_SPEC, partial=False)
    if isinstance(data.get("stock"), bool) or not isinstance(data.get("stock"), int) or data["stock"] < 0:
        raise ValidationError("'stock' must be a non-negative whole number")
    db = get_db()

    if db.products.find_one({"sku": data["sku"]}):
        raise ValidationError(f"SKU '{data['sku']}' already exists")
    if data.get("barcode") and db.products.find_one({"barcode": data["barcode"]}):
        raise ValidationError(f"ברקוד '{data['barcode']}' כבר קיים במוצר אחר")

    last = db.products.find_one(sort=[("_id", -1)])
    new_id = (last["_id"] + 1) if last else 1

    doc = dict(data)
    doc["_id"] = new_id
    doc.setdefault("oldPrice", None)
    doc.setdefault("badge", None)
    doc.setdefault("status", "active")
    doc.setdefault("sold", 0)
    doc.setdefault("image", None)
    doc.setdefault("thumbnail", None)
    # Deliberately NOT `doc.setdefault("barcode", None)`: the barcode index
    # is unique+sparse, and MongoDB's "sparse" only excludes a document
    # that's missing the field entirely — a document with barcode:null is
    # still indexed, so a second product without a barcode would collide
    # with the first and fail to insert. An absent/blank barcode must stay
    # a genuinely absent key, never an explicit null.
    if not doc.get("barcode"):
        doc.pop("barcode", None)

    db.products.insert_one(doc)
    return serialize(doc)


DEFAULT_INVENTORY_REASON = "עדכון ידני"


def update_product(product_id, patch, actor=None):
    # `reason` describes a stock change for the inventory log — it's not a
    # product field, so it never reaches validate_fields/$set. `actor`
    # (the authenticated admin making the change — never client-supplied)
    # is passed in separately by the route, same reasoning.
    reason = patch.get("reason")
    validate_fields(patch, PRODUCT_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("id", "_id", "reason")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    if "stock" in patch:
        if isinstance(patch["stock"], bool) or not isinstance(patch["stock"], int):
            raise ValidationError("'stock' must be a whole number")
        if patch["stock"] < 0:
            raise ValidationError("המלאי אינו יכול להיות שלילי")

    db = get_db()
    before = db.products.find_one({"_id": product_id}, {"stock": 1, "status": 1, "name": 1})
    if not before:
        return None

    # Same sparse+unique-index reasoning as create_product: an explicit
    # `barcode: null/""` must clear the field (via $unset), never sit in
    # $set as a literal null — a literal null is what caused the second
    # product without a barcode to collide with the first.
    unset_barcode = False
    if "barcode" in patch and not patch["barcode"]:
        del patch["barcode"]
        unset_barcode = True
    elif patch.get("barcode"):
        existing_with_barcode = db.products.find_one({"barcode": patch["barcode"], "_id": {"$ne": product_id}})
        if existing_with_barcode:
            raise ValidationError(f"ברקוד '{patch['barcode']}' כבר קיים במוצר אחר")

    # Business rule: stock and status stay consistent even when a caller
    # (e.g. an inventory-only update) only sends `stock`. Explicit `status`
    # in the patch always wins — a product intentionally set to "draft" by
    # an admin isn't silently reactivated just because it was restocked.
    if "stock" in patch and "status" not in patch:
        current_status = before.get("status", "active")
        if patch["stock"] <= 0:
            patch["status"] = "out"
        elif current_status == "out":
            patch["status"] = "active"

    update_doc = {}
    if patch:
        update_doc["$set"] = patch
    if unset_barcode:
        update_doc["$unset"] = {"barcode": ""}

    result = db.products.find_one_and_update(
        {"_id": product_id},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )

    if result is not None and "stock" in patch and patch["stock"] != before.get("stock"):
        # A real, persisted inventory record — not a visual-only history.
        # Covers both the dedicated inventory-adjust action and a stock
        # edit made through the full product-edit form; either way, every
        # actual stock change is accounted for.
        db.inventory_log.insert_one({
            "productId": product_id,
            "productName": result.get("name", before.get("name")),
            "previousStock": before.get("stock", 0),
            "newStock": patch["stock"],
            "delta": patch["stock"] - before.get("stock", 0),
            "reason": (reason or "").strip() or DEFAULT_INVENTORY_REASON,
            "actor": actor,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    return serialize(result)


def delete_product(product_id):
    db = get_db()
    result = db.products.delete_one({"_id": product_id})
    return result.deleted_count > 0


def list_inventory_log(product_id=None, page=1, page_size=50):
    """The inventory_log collection grows without bound (one row per
    stock change, forever), so this is always paginated — never a bare
    unbounded find(). Newest first."""
    db = get_db()
    query = {"productId": product_id} if product_id is not None else {}
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total = db.inventory_log.count_documents(query)
    docs = (
        db.inventory_log.find(query)
        .sort("at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for d in docs:
        item = dict(d)
        item["id"] = str(item.pop("_id"))
        items.append(item)
    return {"items": items, "total": total, "page": page, "pageSize": page_size}
