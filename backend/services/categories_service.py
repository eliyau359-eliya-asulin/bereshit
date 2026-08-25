from pymongo import ReturnDocument

from backend.db.mongo import get_db
from backend.models.schemas import validate_fields, CATEGORY_SPEC, ValidationError


def _serialize(doc):
    """Categories use `key` as their business id field (see shared/models.js's
    Category typedef) — not `id` like every other collection — because that's
    the field name the existing frontend was already built against."""
    if doc is None:
        return None
    out = dict(doc)
    out["key"] = out.pop("_id")
    return out


def list_categories():
    db = get_db()
    # Sort by the curated `order` field (falls back to insertion order for
    # any category created later without one), not by _id — _id sorts
    # alphabetically and would scramble the storefront's category nav.
    docs = db.categories.find().sort("order", 1)
    return [_serialize(d) for d in docs]


def get_category(key):
    db = get_db()
    return _serialize(db.categories.find_one({"_id": key}))


def create_category(data):
    validate_fields(data, CATEGORY_SPEC, partial=False)
    db = get_db()

    key = data["key"].strip()
    if not key:
        raise ValidationError("'key' cannot be empty")
    if db.categories.find_one({"_id": key}):
        raise ValidationError(f"Category key '{key}' already exists")

    last = db.categories.find_one(sort=[("order", -1)])
    next_order = (last["order"] + 1) if last and "order" in last else db.categories.count_documents({})

    doc = {
        "_id": key,
        "label": data["label"],
        "status": data.get("status", "active"),
        "order": data.get("order", next_order),
    }
    db.categories.insert_one(doc)
    return _serialize(doc)


def update_category(key, patch):
    validate_fields(patch, CATEGORY_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k not in ("key", "_id")}
    if not patch:
        raise ValidationError("No updatable fields were provided")

    db = get_db()
    result = db.categories.find_one_and_update(
        {"_id": key},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(result)


def delete_category(key):
    """Refuses to delete a category that still has products assigned to it
    (returns the count so the caller/UI can tell the admin exactly what to
    reassign or remove first) rather than silently orphaning those products."""
    db = get_db()
    if not db.categories.find_one({"_id": key}):
        return {"deleted": False, "reason": "not_found"}

    product_count = db.products.count_documents({"cat": key})
    if product_count > 0:
        return {"deleted": False, "reason": "in_use", "productCount": product_count}

    db.categories.delete_one({"_id": key})
    return {"deleted": True}
