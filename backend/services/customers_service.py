from db.mongo import get_db
from services.common import serialize, serialize_many


def list_customers():
    db = get_db()
    return serialize_many(db.customers.find().sort("_id", 1))


def get_customer(customer_id):
    db = get_db()
    return serialize(db.customers.find_one({"_id": customer_id}))
