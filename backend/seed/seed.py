"""
Seeds MongoDB with the starting catalog. Safe to re-run: each collection
listed below is cleared and reloaded, so the database ends up exactly
matching seed_data.py.

Usage (from the BERESHIT project root):
    python -m backend.seed.seed
"""
from backend.config import Config
from backend.db.mongo import get_db, create_indexes, ping
from backend.seed.seed_data import PRODUCTS, CATEGORIES, CUSTOMERS, ORDERS, PROMOTIONS, STORE_INFO


def _with_mongo_id(doc):
    d = dict(doc)
    d["_id"] = d.pop("id")
    return d


def run():
    Config.validate()
    print(f"Connecting to MongoDB...")
    ping()
    db = get_db()
    print(f"Connected. Database: '{db.name}'")

    collections = {
        "products": PRODUCTS,
        "categories": CATEGORIES,
        "customers": CUSTOMERS,
        "orders": ORDERS,
        "promotions": PROMOTIONS,
    }

    for name, docs in collections.items():
        db[name].delete_many({})
        db[name].insert_many([_with_mongo_id(d) for d in docs])
        print(f"  {name}: seeded {len(docs)} documents")

    db.store_info.delete_many({})
    db.store_info.insert_one(_with_mongo_id(STORE_INFO))
    print("  store_info: seeded 1 document")

    create_indexes(db)
    print("Indexes created.")
    print("Seed complete.")


if __name__ == "__main__":
    run()
