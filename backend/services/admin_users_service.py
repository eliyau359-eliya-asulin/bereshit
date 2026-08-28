from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.db.mongo import get_db
from backend.models.schemas import (
    validate_fields, ADMIN_USER_CREATE_SPEC, ADMIN_USER_UPDATE_SPEC, ValidationError,
)
from backend.auth.roles import ADMIN_ROLES
from backend.auth.security import hash_password, verify_password
from backend.auth.session_store import delete_all_sessions_for_user, TYPE_ADMIN


def _public(doc):
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = out.pop("_id")
    out.pop("passwordHash", None)
    return out


def list_admin_users():
    db = get_db()
    return [_public(d) for d in db.admin_users.find().sort("createdAt", 1)]


def get_admin_user(admin_id):
    db = get_db()
    return _public(db.admin_users.find_one({"_id": admin_id}))


def create_admin_user(data):
    validate_fields(data, ADMIN_USER_CREATE_SPEC, partial=False)
    name = (data["name"] or "").strip()
    email = (data["email"] or "").strip().lower()
    password = data["password"] or ""
    role = data["role"]

    if not name:
        raise ValidationError("שם הוא שדה חובה")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValidationError("כתובת דוא\"ל אינה תקינה")
    if len(password) < 8:
        raise ValidationError("הסיסמה חייבת לכלול לפחות 8 תווים")
    if role not in ADMIN_ROLES:
        raise ValidationError(f"תפקיד לא תקין: '{role}'")

    db = get_db()
    doc = {
        "_id": f"AU-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "name": name,
        "email": email,
        "passwordHash": hash_password(password),
        "role": role,
        "active": True,
        "createdAt": datetime.now(timezone.utc),
    }
    try:
        db.admin_users.insert_one(doc)
    except DuplicateKeyError:
        raise ValidationError("קיים כבר משתמש מנהל עם כתובת דוא\"ל זו")
    return _public(doc)


def update_admin_user(admin_id, patch):
    validate_fields(patch, ADMIN_USER_UPDATE_SPEC, partial=True)
    patch = {k: v for k, v in patch.items() if k in ("name", "role", "active")}
    if not patch:
        raise ValidationError("No updatable fields were provided")
    if "role" in patch and patch["role"] not in ADMIN_ROLES:
        raise ValidationError(f"תפקיד לא תקין: '{patch['role']}'")

    db = get_db()
    result = db.admin_users.find_one_and_update(
        {"_id": admin_id}, {"$set": patch}, return_document=ReturnDocument.AFTER,
    )
    if result is not None and patch.get("active") is False:
        # Deactivating an admin must actually cut off access immediately,
        # not just prevent future logins.
        delete_all_sessions_for_user(TYPE_ADMIN, admin_id)
    return _public(result)


def authenticate_admin(email, password):
    db = get_db()
    email = (email or "").strip().lower()
    admin = db.admin_users.find_one({"email": email})
    if not admin or not admin.get("active", True):
        return None
    if not verify_password(password, admin.get("passwordHash")):
        return None
    return admin


def count_admin_users():
    db = get_db()
    return db.admin_users.count_documents({})
