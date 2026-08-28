from datetime import date

from pymongo.errors import DuplicateKeyError

from backend.db.mongo import get_db, next_sequence
from backend.services.common import serialize, paginate
from backend.models.schemas import validate_fields, CUSTOMER_REGISTER_SPEC, ValidationError
from backend.auth.security import hash_password, verify_password


def _public_customer(doc):
    """Same as serialize(), but never leaks passwordHash to any client."""
    out = serialize(doc)
    if out is not None:
        out.pop("passwordHash", None)
    return out


def list_customers(page=None, page_size=None):
    db = get_db()
    if page is not None:
        cursor = db.customers.find().sort("_id", 1)
        result = paginate(cursor, lambda: db.customers.count_documents({}), page, page_size or 50)
        for item in result["items"]:
            item.pop("passwordHash", None)
        return result
    return [_public_customer(d) for d in db.customers.find().sort("_id", 1)]


def get_customer(customer_id):
    db = get_db()
    return _public_customer(db.customers.find_one({"_id": customer_id}))


def register_customer(data):
    """Creates a new account, or — if a guest checkout already created a
    customer record under this email (no password set) — attaches a
    password to that existing record, turning it into a real account
    without losing its order history. A record that already has a
    password cannot be silently re-registered.

    Note: there is no email-sending/verification step in this system (no
    email provider is configured), so this "claim by email" is not proof
    of ownership beyond knowing the address itself — acceptable for this
    store's threat model today, but worth revisiting if a transactional
    email provider is ever added.
    """
    validate_fields(data, CUSTOMER_REGISTER_SPEC, partial=False)
    name = (data["name"] or "").strip()
    email = (data["email"] or "").strip().lower()
    phone = (data["phone"] or "").strip()
    password = data["password"] or ""

    if not name:
        raise ValidationError("שם הוא שדה חובה")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValidationError("כתובת דוא\"ל אינה תקינה")
    if not phone:
        raise ValidationError("מספר טלפון הוא שדה חובה")
    if len(password) < 8:
        raise ValidationError("הסיסמה חייבת לכלול לפחות 8 תווים")

    db = get_db()
    password_hash = hash_password(password)
    existing = db.customers.find_one({"email": email})

    if existing:
        if existing.get("passwordHash"):
            raise ValidationError("קיים כבר חשבון עם כתובת דוא\"ל זו")
        db.customers.update_one(
            {"_id": existing["_id"]},
            {"$set": {"passwordHash": password_hash, "name": name, "phone": phone}},
        )
        # Reflect the just-written name/phone back, not the pre-update
        # values — otherwise the register response (and the frontend's
        # CURRENT_CUSTOMER built from it) shows the customer's old guest-
        # checkout name until their next full session refresh.
        existing["passwordHash"] = password_hash
        existing["name"] = name
        existing["phone"] = phone
        return _public_customer(existing)

    doc = {
        "_id": f"CU-{next_sequence(db, 'customer_id')}",
        "name": name,
        "email": email,
        "phone": phone,
        "passwordHash": password_hash,
        "orders": 0,
        "spent": 0,
        "joined": date.today().isoformat(),
    }
    try:
        db.customers.insert_one(doc)
    except DuplicateKeyError:
        raise ValidationError("קיים כבר חשבון עם כתובת דוא\"ל זו")
    return _public_customer(doc)


def authenticate_customer(email, password):
    """Returns the customer doc on success, or None. Deliberately does not
    distinguish "no such email" from "wrong password" in its return value
    — that distinction is exactly what an account-enumeration attack would
    probe for."""
    db = get_db()
    email = (email or "").strip().lower()
    customer = db.customers.find_one({"email": email})
    if not customer or not verify_password(password, customer.get("passwordHash")):
        return None
    return customer


def update_customer_profile(customer_id, patch):
    from backend.models.schemas import CUSTOMER_PROFILE_UPDATE_SPEC
    validate_fields(patch, CUSTOMER_PROFILE_UPDATE_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k in ("name", "phone") and v is not None}
    if not patch:
        raise ValidationError("No updatable fields were provided")
    db = get_db()
    from pymongo import ReturnDocument
    result = db.customers.find_one_and_update(
        {"_id": customer_id}, {"$set": patch}, return_document=ReturnDocument.AFTER,
    )
    return _public_customer(result)


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
