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
