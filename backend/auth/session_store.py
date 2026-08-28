"""Server-side sessions backed by MongoDB (a `sessions` collection with a
TTL index on `expiresAt` — see create_indexes in backend/db/mongo.py).
The cookie only ever carries an opaque random token; every request looks
that token up here to resolve identity. This is what makes logout a real
action (delete the row) rather than just "the client forgot a value."
"""
from datetime import datetime, timedelta, timezone

from backend.db.mongo import get_db
from backend.auth.security import new_session_token, hash_token

ADMIN_SESSION_TTL = timedelta(hours=12)
CUSTOMER_SESSION_TTL = timedelta(days=14)

TYPE_ADMIN = "admin"
TYPE_CUSTOMER = "customer"


def create_session(user_type, user_id, role=None, name=None):
    db = get_db()
    token = new_session_token()
    ttl = ADMIN_SESSION_TTL if user_type == TYPE_ADMIN else CUSTOMER_SESSION_TTL
    now = datetime.now(timezone.utc)
    doc = {
        "_id": hash_token(token),
        "userType": user_type,
        "userId": user_id,
        "role": role,
        "name": name,  # denormalized so routes can attribute an action (e.g. an inventory_log entry) without an extra lookup
        "createdAt": now,
        "expiresAt": now + ttl,
    }
    db.sessions.insert_one(doc)
    return token, doc["expiresAt"]


def get_session(token):
    if not token:
        return None
    db = get_db()
    doc = db.sessions.find_one({"_id": hash_token(token)})
    if not doc:
        return None
    expires_at = doc["expiresAt"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        # Belt-and-suspenders: the TTL index reaps expired rows in the
        # background (checked ~once/minute), so a request landing in that
        # window must not treat a stale-but-not-yet-deleted row as valid.
        db.sessions.delete_one({"_id": doc["_id"]})
        return None
    return doc


def delete_session(token):
    if not token:
        return
    db = get_db()
    db.sessions.delete_one({"_id": hash_token(token)})


def delete_all_sessions_for_user(user_type, user_id):
    """Used when a password changes or an admin account is deactivated —
    invalidates every existing session for that user immediately."""
    db = get_db()
    db.sessions.delete_many({"userType": user_type, "userId": user_id})
