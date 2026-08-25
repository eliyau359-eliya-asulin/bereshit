from db.mongo import get_db


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
