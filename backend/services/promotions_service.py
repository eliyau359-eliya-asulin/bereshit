from pymongo import ReturnDocument

from backend.db.mongo import get_db
from backend.models.schemas import validate_fields, PROMOTION_SPEC, ValidationError
from backend.services.common import serialize, serialize_many


def list_promotions():
    db = get_db()
    return serialize_many(db.promotions.find().sort("start", 1))


def get_promotion(promo_id):
    db = get_db()
    return serialize(db.promotions.find_one({"_id": promo_id}))


def create_promotion(data):
    validate_fields(data, PROMOTION_SPEC, partial=False)
    db = get_db()

    if db.promotions.find_one({"code": data["code"]}):
        raise ValidationError(f"Coupon code '{data['code']}' already exists")

    last = db.promotions.find_one(sort=[("_id", -1)])
    next_num = int(last["_id"].split("-")[1]) + 1 if last else 1
    new_id = f"PR-{next_num:02d}"

    doc = dict(data)
    doc["_id"] = new_id
    doc.setdefault("status", "scheduled")

    db.promotions.insert_one(doc)
    return serialize(doc)


def update_promotion(promo_id, patch):
    validate_fields(patch, PROMOTION_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("id", "_id")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    db = get_db()
    result = db.promotions.find_one_and_update(
        {"_id": promo_id},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return serialize(result)
