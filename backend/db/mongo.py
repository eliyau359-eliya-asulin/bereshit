"""
PyMongo connection singleton. Every collection accessor in services/ goes
through get_db() — this is the one place that knows how to reach MongoDB.
"""
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConfigurationError

from config import Config

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

    db.orders.create_index([("customerId", ASCENDING)])
    db.orders.create_index([("status", ASCENDING)])
    db.orders.create_index([("date", ASCENDING)])

    db.customers.create_index([("email", ASCENDING)], unique=True)

    db.promotions.create_index([("code", ASCENDING)], unique=True)
    db.promotions.create_index([("status", ASCENDING)])
