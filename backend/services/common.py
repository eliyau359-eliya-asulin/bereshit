"""Shared helpers for the service layer: MongoDB stores the business id
(product id, order id, category key, ...) directly as `_id` — see the
module docstring in services/products_service.py for why. These helpers
translate between Mongo's `_id` and the `id` field the frontend/API use."""


def serialize(doc):
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = out.pop("_id")
    return out


def serialize_many(docs):
    return [serialize(d) for d in docs]


def paginate(cursor, count_query_fn, page, page_size):
    """Applied only when the caller explicitly asks for a page (keeps every
    existing list endpoint returning a bare array by default — no response
    shape change for callers that don't opt in). `count_query_fn` is a
    zero-arg callable returning the total matching document count."""
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total = count_query_fn()
    docs = cursor.skip((page - 1) * page_size).limit(page_size)
    return {"items": serialize_many(docs), "total": total, "page": page, "pageSize": page_size}
