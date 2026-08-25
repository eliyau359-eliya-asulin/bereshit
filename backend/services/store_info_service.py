"""Store info is a singleton document — one row describing the shop itself."""
from pymongo import ReturnDocument

from db.mongo import get_db
from models.schemas import validate_fields, STORE_INFO_SPEC, ValidationError
from services.common import serialize

STORE_INFO_ID = "store_info"


def get_store_info():
    db = get_db()
    return serialize(db.store_info.find_one({"_id": STORE_INFO_ID}))


def update_store_info(patch):
    validate_fields(patch, STORE_INFO_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("id", "_id")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    db = get_db()
    result = db.store_info.find_one_and_update(
        {"_id": STORE_INFO_ID},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        upsert=True,
    )
    return serialize(result)
