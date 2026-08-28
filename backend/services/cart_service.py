"""Server-side cart for authenticated customers only — a guest's cart
stays purely client-side (localStorage), never touches this collection.
The cart never reserves inventory (no stock is touched here); it is
revalidated for real at checkout, same as it always was. This is just a
place for a logged-in customer's cart to live so it survives across
devices/sessions instead of being trapped in one browser's localStorage.
"""
from datetime import datetime, timezone

from backend.db.mongo import get_db
from backend.models.schemas import ValidationError

MAX_LINE_ITEMS = 200
MAX_QTY_PER_ITEM = 99


def _clean_items(items):
    if not isinstance(items, list):
        raise ValidationError("עגלת הקניות חייבת להיות רשימה")
    if len(items) > MAX_LINE_ITEMS:
        raise ValidationError("עגלת הקניות מכילה יותר מדי פריטים")
    cleaned = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        pid = it.get("productId") or it.get("id")
        qty = it.get("qty")
        if isinstance(pid, bool) or not isinstance(pid, int):
            continue
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            continue
        qty = min(qty, MAX_QTY_PER_ITEM)
        # Same product listed twice in one payload -> combine rather than
        # keep whichever line happened to be last (mirrors the merge logic
        # the frontend already does for guest+account cart merges).
        cleaned[pid] = min(cleaned.get(pid, 0) + qty, MAX_QTY_PER_ITEM)
    return [{"productId": pid, "qty": qty} for pid, qty in cleaned.items()]


def get_cart(customer_id):
    db = get_db()
    doc = db.carts.find_one({"_id": customer_id})
    return doc["items"] if doc else []


def save_cart(customer_id, items):
    db = get_db()
    clean = _clean_items(items)
    db.carts.update_one(
        {"_id": customer_id},
        {"$set": {"items": clean, "updatedAt": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return clean
