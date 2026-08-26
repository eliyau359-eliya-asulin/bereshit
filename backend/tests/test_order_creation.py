"""
Integration tests for the real order-creation pipeline (POST /api/orders).

Runs against the project's actual configured MongoDB (there is no
separate test database for this project) using Flask's test client, so
no server needs to be running on :5000 for these tests. Every test
creates its own uniquely-id'd throwaway products/customers/orders and
deletes them again in a fixture teardown, so the suite is repeatable and
never touches the real seeded demo catalog (ids 1-17, CU-201.., etc.).

Run with (from the project root):
    pip install -r backend/requirements-dev.txt
    python -m pytest backend/tests -v
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, for `import backend...`

from backend.app import app as flask_app
from backend.db.mongo import get_db

# Test data lives in a dedicated id range far above the seeded catalog
# (products 1-17, customers CU-201..CU-212) so it can never collide.
TEST_PRODUCT_ID_START = 900001


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


class Cleanup:
    """Collects ids created during a test and deletes them afterward,
    regardless of whether the test passed, failed, or raised."""
    def __init__(self, db):
        self.db = db
        self.product_ids = []
        self.customer_emails = []
        self.order_ids = []

    def sweep(self):
        if self.product_ids:
            self.db.products.delete_many({"_id": {"$in": self.product_ids}})
        if self.customer_emails:
            self.db.customers.delete_many({"email": {"$in": self.customer_emails}})
        if self.order_ids:
            self.db.orders.delete_many({"_id": {"$in": self.order_ids}})


@pytest.fixture()
def cleanup(db):
    c = Cleanup(db)
    yield c
    c.sweep()


def make_product(db, pid, stock, price=100, status="active", sku=None):
    doc = {
        "_id": pid,
        "sku": sku or f"TEST-{pid}",
        "cat": "gifts", "catLabel": "מתנות",
        "name": f"מוצר בדיקה {pid}",
        "price": price, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": stock, "threshold": 2, "status": status, "sold": 0, "image": None,
    }
    db.products.delete_one({"_id": pid})
    db.products.insert_one(doc)
    return doc


def unique_email():
    return f"qa.{uuid.uuid4().hex[:10]}@example.com"


def checkout_payload(items, email=None, name="בדיקה אוטומטית", phone="050-0000000",
                      city="תל אביב", address="רחוב הבדיקה 1"):
    return {
        "customer": {"name": name, "email": email or unique_email(), "phone": phone},
        "shipping": {"method": "standard", "address": address, "city": city, "zip": "6100000"},
        "items": items,
        "payment": {"method": "cash_on_delivery"},
    }


# ---------------------------------------------------------------------
# TEST 1 — valid order -> 201, order exists in MongoDB
# ---------------------------------------------------------------------
def test_valid_order_creates_order_in_mongodb(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 1
    make_product(db, pid, stock=10, price=100)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 2}])
    cleanup.customer_emails.append(payload["customer"]["email"])

    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])

    stored = db.orders.find_one({"_id": order["id"]})
    assert stored is not None
    assert stored["items"][0]["productId"] == pid
    assert stored["items"][0]["qty"] == 2


# ---------------------------------------------------------------------
# TEST 2 — nonexistent product -> 400, no order created
# ---------------------------------------------------------------------
def test_nonexistent_product_returns_400_and_creates_nothing(client, db, cleanup):
    fake_pid = TEST_PRODUCT_ID_START + 2  # deliberately never inserted
    payload = checkout_payload([{"productId": fake_pid, "qty": 1}])
    cleanup.customer_emails.append(payload["customer"]["email"])

    orders_before = db.orders.count_documents({})
    res = client.post("/api/orders", json=payload)

    assert res.status_code == 400
    assert "error" in res.get_json()
    assert db.orders.count_documents({}) == orders_before


# ---------------------------------------------------------------------
# TEST 3 — qty > stock -> 400, no order, stock unchanged
# ---------------------------------------------------------------------
def test_insufficient_stock_returns_400_and_leaves_stock_unchanged(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 3
    make_product(db, pid, stock=3, price=50)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 5}])
    cleanup.customer_emails.append(payload["customer"]["email"])

    orders_before = db.orders.count_documents({})
    res = client.post("/api/orders", json=payload)

    assert res.status_code == 400
    assert "אינו זמין במלאי" in res.get_json()["error"]
    assert db.orders.count_documents({}) == orders_before
    assert db.products.find_one({"_id": pid})["stock"] == 3  # untouched


# ---------------------------------------------------------------------
# TEST 4 — qty == stock -> success, stock becomes 0, status becomes "out"
# ---------------------------------------------------------------------
def test_exact_stock_quantity_succeeds_and_flips_status_to_out(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 4
    make_product(db, pid, stock=4, price=75)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 4}])
    cleanup.customer_emails.append(payload["customer"]["email"])

    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    cleanup.order_ids.append(res.get_json()["order"]["id"])

    product = db.products.find_one({"_id": pid})
    assert product["stock"] == 0
    assert product["status"] == "out"
    assert product["sold"] == 4


# ---------------------------------------------------------------------
# TEST 5 — server ignores client-supplied price
# ---------------------------------------------------------------------
def test_server_ignores_client_supplied_price(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 5
    make_product(db, pid, stock=10, price=200)
    cleanup.product_ids.append(pid)

    # Client tries to sneak in a fake price/lineTotal/subtotal — the item
    # schema only recognizes productId/qty, so this is simply ignored.
    payload = checkout_payload([{"productId": pid, "qty": 1, "price": 1, "lineTotal": 1}])
    payload["subtotal"] = 1
    payload["total"] = 1
    cleanup.customer_emails.append(payload["customer"]["email"])

    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])

    assert order["subtotal"] == 200  # real MongoDB price, not the client's "1"
    stored = db.orders.find_one({"_id": order["id"]})
    assert stored["items"][0]["price"] == 200
    assert stored["items"][0]["lineTotal"] == 200
    assert stored["total"] == 200


# ---------------------------------------------------------------------
# TEST 6 — shipping calculated from store-info, not hardcoded
# ---------------------------------------------------------------------
def test_shipping_calculated_from_store_info(client, db, cleanup):
    store_info = db.store_info.find_one({"_id": "store_info"})
    ship_cost = store_info["shippingCost"]
    free_threshold = store_info["freeShippingThreshold"]

    # Below the free-shipping threshold -> real shippingCost is charged.
    pid_low = TEST_PRODUCT_ID_START + 6
    cheap_price = min(50, max(1, free_threshold - 1))
    make_product(db, pid_low, stock=5, price=cheap_price)
    cleanup.product_ids.append(pid_low)
    payload = checkout_payload([{"productId": pid_low, "qty": 1}])
    cleanup.customer_emails.append(payload["customer"]["email"])
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])
    assert order["shipping"] == ship_cost
    assert order["total"] == order["subtotal"] + ship_cost

    # At/above the threshold -> shipping is free.
    pid_high = TEST_PRODUCT_ID_START + 7
    make_product(db, pid_high, stock=5, price=free_threshold)
    cleanup.product_ids.append(pid_high)
    payload2 = checkout_payload([{"productId": pid_high, "qty": 1}])
    cleanup.customer_emails.append(payload2["customer"]["email"])
    res2 = client.post("/api/orders", json=payload2)
    assert res2.status_code == 201, res2.get_json()
    order2 = res2.get_json()["order"]
    cleanup.order_ids.append(order2["id"])
    assert order2["shipping"] == 0
    assert order2["total"] == order2["subtotal"]


# ---------------------------------------------------------------------
# TEST 7 — existing customer email -> no duplicate customer created
# ---------------------------------------------------------------------
def test_existing_customer_email_is_reused_not_duplicated(client, db, cleanup):
    email = unique_email()
    cleanup.customer_emails.append(email)
    existing = {
        "_id": "CU-TESTFIXED-1", "name": "לקוח קיים", "email": email,
        "phone": "050-1111111", "orders": 0, "spent": 0, "joined": "2026-01-01",
    }
    db.customers.delete_one({"_id": existing["_id"]})
    db.customers.insert_one(existing)

    pid = TEST_PRODUCT_ID_START + 8
    make_product(db, pid, stock=10, price=60)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 1}], email=email, name="שם אחר בקופה")
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])

    assert order["customerId"] == existing["_id"]
    assert db.customers.count_documents({"email": email}) == 1  # still exactly one

    db.customers.delete_one({"_id": existing["_id"]})


# ---------------------------------------------------------------------
# TEST 8 — new customer email -> customer created
# ---------------------------------------------------------------------
def test_new_customer_email_creates_customer(client, db, cleanup):
    email = unique_email()
    cleanup.customer_emails.append(email)
    assert db.customers.find_one({"email": email}) is None

    pid = TEST_PRODUCT_ID_START + 9
    make_product(db, pid, stock=10, price=40)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 1}], email=email, name="לקוח חדש")
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])

    created = db.customers.find_one({"email": email})
    assert created is not None
    assert created["_id"] == order["customerId"]
    assert created["name"] == "לקוח חדש"
    assert created["orders"] == 1
    assert created["spent"] == 40


# ---------------------------------------------------------------------
# TEST 9 — multiple products -> all line totals and total correct
# ---------------------------------------------------------------------
def test_multiple_products_line_totals_and_total_correct(client, db, cleanup):
    pid_a = TEST_PRODUCT_ID_START + 10
    pid_b = TEST_PRODUCT_ID_START + 11
    make_product(db, pid_a, stock=10, price=120)
    make_product(db, pid_b, stock=10, price=45)
    cleanup.product_ids += [pid_a, pid_b]

    payload = checkout_payload([
        {"productId": pid_a, "qty": 2},
        {"productId": pid_b, "qty": 3},
    ])
    cleanup.customer_emails.append(payload["customer"]["email"])

    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    cleanup.order_ids.append(order["id"])

    stored = db.orders.find_one({"_id": order["id"]})
    items = {it["productId"]: it for it in stored["items"]}
    assert items[pid_a]["lineTotal"] == 240
    assert items[pid_b]["lineTotal"] == 135
    expected_subtotal = 240 + 135
    assert stored["total"] == expected_subtotal
    assert order["subtotal"] == expected_subtotal


# ---------------------------------------------------------------------
# TEST 10 — successful order -> Admin API can retrieve it
# ---------------------------------------------------------------------
def test_admin_can_retrieve_created_order(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 12
    make_product(db, pid, stock=10, price=90)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(payload["customer"]["email"])

    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order_id = res.get_json()["order"]["id"]
    cleanup.order_ids.append(order_id)

    # Same endpoint the admin dashboard uses to list/read orders.
    get_res = client.get(f"/api/orders/{order_id}")
    assert get_res.status_code == 200
    fetched = get_res.get_json()
    assert fetched["id"] == order_id
    assert fetched["status"] == "ממתין לאישור"
    assert fetched["pay"] == "ממתין לתשלום"

    list_res = client.get("/api/orders")
    assert list_res.status_code == 200
    assert any(o["id"] == order_id for o in list_res.get_json())
