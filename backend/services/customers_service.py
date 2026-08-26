from datetime import date

from pymongo.errors import DuplicateKeyError

from backend.db.mongo import get_db, next_sequence
from backend.services.common import serialize, serialize_many


def list_customers():
    db = get_db()
    return serialize_many(db.customers.find().sort("_id", 1))


def get_customer(customer_id):
    db = get_db()
    return serialize(db.customers.find_one({"_id": customer_id}))


def find_or_create_customer(name, email, phone):
    """Reuses an existing customer by normalized (trimmed, lowercased)
    email, or creates a new one. Race-safe: the unique index on `email`
    means that if two checkouts with the same brand-new email land at the
    same time, the loser's insert raises DuplicateKeyError and it simply
    re-fetches the winner's document instead of creating a duplicate.

    Intentionally NOT run inside the order's transaction — a customer
    record created just before an order that then fails validation isn't
    a data-integrity problem (a customer can exist with zero orders), and
    keeping it out avoids a duplicate-key error hard-aborting that
    transaction.
    """
    db = get_db()
    normalized_email = (email or "").strip().lower()

    existing = db.customers.find_one({"email": normalized_email})
    if existing:
        return existing

    doc = {
        "_id": f"CU-{next_sequence(db, 'customer_id')}",
        "name": name,
        "email": normalized_email,
        "phone": phone,
        "orders": 0,
        "spent": 0,
        "joined": date.today().isoformat(),
    }
    try:
        db.customers.insert_one(doc)
        return doc
    except DuplicateKeyError:
        return db.customers.find_one({"email": normalized_email})
