from pymongo import ReturnDocument

from backend.db.mongo import get_db
from backend.models.schemas import (
    validate_fields, ORDER_UPDATE_SPEC, ValidationError,
    ORDER_STATUS_FLOW, ORDER_CANCELLABLE_FROM,
)
from backend.services.common import serialize, serialize_many


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
