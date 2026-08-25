from pymongo import ReturnDocument

from db.mongo import get_db
from models.schemas import validate_fields, ORDER_UPDATE_SPEC, ValidationError
from services.common import serialize, serialize_many


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
    result = db.orders.find_one_and_update(
        {"_id": order_id},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return serialize(result)
