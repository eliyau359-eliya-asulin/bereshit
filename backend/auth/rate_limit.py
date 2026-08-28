"""Login brute-force protection, backed by MongoDB (not in-process memory)
so it works correctly across Vercel's serverless instances — an
in-memory counter would reset per-instance and give no real protection.

Two independent caps apply to every login attempt:
  - per source IP + scope (stops one attacker hammering many accounts)
  - per account + scope (stops credential stuffing from rotating IPs)
Whichever is hit first blocks the request. Both windows are fixed and
self-expire via a TTL index — no cleanup job needed.
"""
from datetime import datetime, timedelta, timezone

from flask import request

from backend.db.mongo import get_db


def client_ip():
    """Vercel (and most reverse proxies) puts the real client address in
    X-Forwarded-For; request.remote_addr alone would just be the proxy's
    address for every request, making IP-based limiting useless."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"

WINDOW = timedelta(minutes=15)
MAX_PER_IP = 20
MAX_PER_ACCOUNT = 8


def _bump(key):
    """Atomically increments a fixed-window counter, creating it (with a
    TTL-backed expiry) on first use. Returns the count after this attempt."""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = db.login_attempts.find_one_and_update(
        {"_id": key, "expiresAt": {"$gt": now}},
        {"$inc": {"count": 1}},
        upsert=False,
    )
    if doc is None:
        db.login_attempts.update_one(
            {"_id": key},
            {"$set": {"count": 1, "expiresAt": now + WINDOW}},
            upsert=True,
        )
        return 1
    return doc["count"] + 1


def register_failed_attempt(scope, ip, account_key):
    """Call after a failed login. `scope` is 'admin' or 'customer'."""
    _bump(f"ip:{scope}:{ip}")
    if account_key:
        _bump(f"acct:{scope}:{account_key}")


def is_locked_out(scope, ip, account_key):
    db = get_db()
    now = datetime.now(timezone.utc)
    ip_doc = db.login_attempts.find_one({"_id": f"ip:{scope}:{ip}", "expiresAt": {"$gt": now}})
    if ip_doc and ip_doc["count"] >= MAX_PER_IP:
        return True
    if account_key:
        acct_doc = db.login_attempts.find_one({"_id": f"acct:{scope}:{account_key}", "expiresAt": {"$gt": now}})
        if acct_doc and acct_doc["count"] >= MAX_PER_ACCOUNT:
            return True
    return False


def clear_attempts(scope, ip, account_key):
    """Call after a successful login — a legitimate user who mistyped
    their password a couple of times shouldn't stay throttled."""
    db = get_db()
    db.login_attempts.delete_many({"_id": {"$in": [f"ip:{scope}:{ip}", f"acct:{scope}:{account_key}"]}})
