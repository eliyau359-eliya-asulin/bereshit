"""
Products are stored with MongoDB's `_id` set to the same numeric id the
frontend already used (shared/mock-data.js, admin/js/data.js) — so a
product id is identical across Admin, the API, MongoDB, and the customer
site, exactly as requested: PUT /api/products/123 updates _id=123.
"""
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


def create_product(data):
    validate_fields(data, PRODUCT_SPEC, partial=False)
    db = get_db()

    if db.products.find_one({"sku": data["sku"]}):
        raise ValidationError(f"SKU '{data['sku']}' already exists")

    last = db.products.find_one(sort=[("_id", -1)])
    new_id = (last["_id"] + 1) if last else 1

    doc = dict(data)
    doc["_id"] = new_id
    doc.setdefault("oldPrice", None)
    doc.setdefault("badge", None)
    doc.setdefault("status", "active")
    doc.setdefault("sold", 0)

    db.products.insert_one(doc)
    return serialize(doc)


def update_product(product_id, patch):
    validate_fields(patch, PRODUCT_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("id", "_id")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    db = get_db()

    # Business rule: stock and status stay consistent even when a caller
    # (e.g. an inventory-only update) only sends `stock`. Explicit `status`
    # in the patch always wins.
    if "stock" in patch and "status" not in patch:
        current = db.products.find_one({"_id": product_id}, {"status": 1})
        current_status = current["status"] if current else "active"
        if patch["stock"] <= 0:
            patch["status"] = "out"
        elif current_status == "out":
            patch["status"] = "active"

    result = db.products.find_one_and_update(
        {"_id": product_id},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return serialize(result)


def delete_product(product_id):
    db = get_db()
    result = db.products.delete_one({"_id": product_id})
    return result.deleted_count > 0
