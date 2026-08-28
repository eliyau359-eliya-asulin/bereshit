"""
PyMongo connection singleton. Every collection accessor in services/ goes
through get_db() — this is the one place that knows how to reach MongoDB.
"""
from pymongo import MongoClient, ASCENDING, ReturnDocument
from pymongo.errors import ConfigurationError

from backend.config import Config

_client = None
_db = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    return _client


def get_db():
    """Returns the database named in MONGODB_URI's path (e.g. '.../Bereshit'),
    falling back to MONGODB_DB_NAME if the URI doesn't specify one."""
    global _db
    if _db is None:
        client = get_client()
        try:
            _db = client.get_default_database()
        except ConfigurationError:
            _db = None
        if _db is None:
            _db = client[Config.MONGODB_DB_NAME]
    return _db


def ping():
    """Raises on failure — used by the /api/health endpoint and startup check."""
    get_client().admin.command("ping")


def create_indexes(db):
    """Indexes for the fields the API actually filters/sorts/looks up by.
    _id is already uniquely indexed by MongoDB for every collection, which
    covers product/order/customer/category id lookups."""
    db.products.create_index([("cat", ASCENDING)])
    db.products.create_index([("status", ASCENDING)])
    db.products.create_index([("sku", ASCENDING)], unique=True)
    # sparse: most products won't have a barcode set, and those should never
    # collide with each other on a "both null" false match.
    db.products.create_index([("barcode", ASCENDING)], unique=True, sparse=True)

    db.orders.create_index([("customerId", ASCENDING)])
    db.orders.create_index([("status", ASCENDING)])
    db.orders.create_index([("date", ASCENDING)])

    db.customers.create_index([("email", ASCENDING)], unique=True)

    db.promotions.create_index([("code", ASCENDING)], unique=True)
    db.promotions.create_index([("status", ASCENDING)])

    db.inventory_log.create_index([("productId", ASCENDING)])
    db.inventory_log.create_index([("at", ASCENDING)])

    db.admin_users.create_index([("email", ASCENDING)], unique=True)

    # TTL index: MongoDB's background task removes a session document once
    # its `expiresAt` is in the past (checked roughly once/minute) — sessions
    # self-clean without any cron job or manual sweep.
    db.sessions.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0)
    db.sessions.create_index([("userType", ASCENDING), ("userId", ASCENDING)])

    db.login_attempts.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0)


def bootstrap_counters(db):
    """Idempotent. The atomic id counters used to mint new order/customer
    ids (see next_sequence) must start above whatever the seed data
    already used, so a real new order/customer can never collide with a
    seeded one. Only touches a counter that doesn't exist yet — safe to
    call on every app startup."""
    if not db.counters.find_one({"_id": "order_id"}):
        max_num = 10233  # one below the first seeded order, BJ-10234
        for o in db.orders.find({}, {"_id": 1}):
            oid = o["_id"]
            if isinstance(oid, str) and oid.startswith("BJ-"):
                try:
                    max_num = max(max_num, int(oid.split("-", 1)[1]))
                except ValueError:
                    pass
        db.counters.update_one({"_id": "order_id"}, {"$setOnInsert": {"seq": max_num}}, upsert=True)

    if not db.counters.find_one({"_id": "customer_id"}):
        max_num = 200  # one below the first seeded customer, CU-201
        for c in db.customers.find({}, {"_id": 1}):
            cid = c["_id"]
            if isinstance(cid, str) and cid.startswith("CU-"):
                try:
                    max_num = max(max_num, int(cid.split("-", 1)[1]))
                except ValueError:
                    pass
        db.counters.update_one({"_id": "customer_id"}, {"$setOnInsert": {"seq": max_num}}, upsert=True)


def bootstrap_admin(db):
    """Idempotent: creates the first Super Admin account from
    ADMIN_BOOTSTRAP_EMAIL/ADMIN_BOOTSTRAP_PASSWORD if backend.admin_users is
    completely empty. Never overwrites or touches an existing admin account,
    and never invents a credential — if the env vars aren't set, this is a
    no-op and the deployment simply has no admin login until one is created
    (see backend/seed/seed_admin.py for a one-off CLI alternative)."""
    from backend.config import Config
    from backend.auth.security import hash_password
    from backend.auth.roles import SUPER_ADMIN
    from datetime import datetime, timezone

    if db.admin_users.count_documents({}) > 0:
        return False
    if not Config.ADMIN_BOOTSTRAP_EMAIL or not Config.ADMIN_BOOTSTRAP_PASSWORD:
        return False

    db.admin_users.insert_one({
        "_id": "AU-1",
        "name": Config.ADMIN_BOOTSTRAP_NAME,
        "email": Config.ADMIN_BOOTSTRAP_EMAIL.strip().lower(),
        "passwordHash": hash_password(Config.ADMIN_BOOTSTRAP_PASSWORD),
        "role": SUPER_ADMIN,
        "active": True,
        "createdAt": datetime.now(timezone.utc),
    })
    return True


def next_sequence(db, name, session=None):
    """Atomically returns the next integer in a named sequence (e.g.
    'order_id', 'customer_id'). Safe under concurrency — MongoDB's $inc
    on a single document is atomic, so two simultaneous callers always
    get two different numbers, never the same one."""
    doc = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    return doc["seq"]
