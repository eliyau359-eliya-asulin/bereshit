"""
Integration tests for the inventory-management system: admin manual stock
updates (backend/services/products_service.py:update_product), the real
inventory_log audit trail, and stock-safety guarantees (no negative stock,
no overselling under concurrency).

Runs against the project's actual configured MongoDB via Flask's test
client, same pattern as test_order_creation.py. All test data lives in a
dedicated id range far above the seeded catalog and is cleaned up after
each test.

Run with (from the project root):
    python -m pytest backend/tests -v
"""
import sys
import threading
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, for `import backend...`

from backend.app import app as flask_app
from backend.db.mongo import get_db

TEST_PRODUCT_ID_START = 910001


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


class Cleanup:
    def __init__(self, db):
        self.db = db
        self.product_ids = []
        self.customer_emails = []
        self.order_ids = []

    def sweep(self):
        if self.product_ids:
            self.db.products.delete_many({"_id": {"$in": self.product_ids}})
            self.db.inventory_log.delete_many({"productId": {"$in": self.product_ids}})
        if self.customer_emails:
            self.db.customers.delete_many({"email": {"$in": self.customer_emails}})
        if self.order_ids:
            self.db.orders.delete_many({"_id": {"$in": self.order_ids}})


@pytest.fixture()
def cleanup(db):
    c = Cleanup(db)
    yield c
    c.sweep()


def make_product(db, pid, stock, price=100, status="active", threshold=2, sku=None):
    doc = {
        "_id": pid,
        "sku": sku or f"TEST-{pid}",
        "cat": "gifts", "catLabel": "מתנות",
        "name": f"מוצר בדיקה {pid}",
        "price": price, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": stock, "threshold": threshold, "status": status, "sold": 0, "image": None,
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
# Admin manual stock update writes a real inventory_log entry
# ---------------------------------------------------------------------
def test_admin_stock_update_writes_inventory_log_with_reason(admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 1
    make_product(db, pid, stock=20)
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": 12, "reason": "מכירה בחנות הפיזית"})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["stock"] == 12

    log = db.inventory_log.find_one({"productId": pid})
    assert log is not None
    assert log["previousStock"] == 20
    assert log["newStock"] == 12
    assert log["delta"] == -8
    assert log["reason"] == "מכירה בחנות הפיזית"
    assert "at" in log
    assert log["actor"]["id"] == "AU-TEST-SUPER-ADMIN"  # from the admin_client fixture — real attribution, not anonymous


def test_admin_stock_update_without_reason_uses_default(admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 2
    make_product(db, pid, stock=5)
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": 9})
    assert res.status_code == 200, res.get_json()

    log = db.inventory_log.find_one({"productId": pid})
    assert log is not None
    assert log["reason"]  # non-empty default, not a fabricated fake history


def test_stock_update_that_does_not_change_stock_writes_no_log(admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 3
    make_product(db, pid, stock=7)
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"name": "שם חדש"})
    assert res.status_code == 200, res.get_json()
    assert db.inventory_log.find_one({"productId": pid}) is None


# ---------------------------------------------------------------------
# Negative / non-integer stock is rejected on the admin path
# ---------------------------------------------------------------------
def test_admin_rejects_negative_stock(admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 4
    make_product(db, pid, stock=5)
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": -1})
    assert res.status_code == 400
    assert db.products.find_one({"_id": pid})["stock"] == 5


def test_admin_rejects_non_integer_stock(admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 5
    make_product(db, pid, stock=5)
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": 3.5})
    assert res.status_code == 400
    assert db.products.find_one({"_id": pid})["stock"] == 5


# ---------------------------------------------------------------------
# Stock 0 -> auto "out"; restock above 0 -> auto "active" again
# ---------------------------------------------------------------------
def test_zeroing_stock_marks_product_out_and_restocking_reactivates(client, admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 6
    make_product(db, pid, stock=3, status="active")
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": 0, "reason": "תיקון מלאי"})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["status"] == "out"

    # Out-of-stock product cannot be purchased even though a checkout might race in.
    payload = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(payload["customer"]["email"])
    order_res = client.post("/api/orders", json=payload)
    assert order_res.status_code == 400

    # Physical correction 0 -> 10 makes it purchasable again automatically.
    res2 = admin_client.put(f"/api/products/{pid}", json={"stock": 10, "reason": "קבלת מלאי חדש"})
    assert res2.status_code == 200, res2.get_json()
    assert res2.get_json()["status"] == "active"

    payload2 = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(payload2["customer"]["email"])
    order_res2 = client.post("/api/orders", json=payload2)
    assert order_res2.status_code == 201, order_res2.get_json()
    cleanup.order_ids.append(order_res2.get_json()["order"]["id"])


def test_explicit_status_in_patch_overrides_stock_auto_sync(admin_client, db, cleanup):
    """A product intentionally set to draft/disabled must not be silently
    reactivated by a restock happening in the same request, and setting
    status explicitly always wins over the stock-derived default."""
    pid = TEST_PRODUCT_ID_START + 7
    make_product(db, pid, stock=0, status="out")
    cleanup.product_ids.append(pid)

    res = admin_client.put(f"/api/products/{pid}", json={"stock": 15, "status": "draft"})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["stock"] == 15
    assert res.get_json()["status"] == "draft"  # explicit status wins, not auto-flipped to "active"


# ---------------------------------------------------------------------
# Full lifecycle from the task spec: 20 -> online -5 -> 15 -> admin -3 ->
# 12 -> online -12 -> 0 -> blocked
# ---------------------------------------------------------------------
def test_full_online_and_physical_stock_lifecycle(client, admin_client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 8
    make_product(db, pid, stock=20)
    cleanup.product_ids.append(pid)

    p1 = checkout_payload([{"productId": pid, "qty": 5}])
    cleanup.customer_emails.append(p1["customer"]["email"])
    r1 = client.post("/api/orders", json=p1)
    assert r1.status_code == 201, r1.get_json()
    cleanup.order_ids.append(r1.get_json()["order"]["id"])
    assert db.products.find_one({"_id": pid})["stock"] == 15

    r2 = admin_client.put(f"/api/products/{pid}", json={"stock": 12, "reason": "מכירה בחנות הפיזית"})
    assert r2.status_code == 200, r2.get_json()
    assert r2.get_json()["stock"] == 12

    p3 = checkout_payload([{"productId": pid, "qty": 12}])
    cleanup.customer_emails.append(p3["customer"]["email"])
    r3 = client.post("/api/orders", json=p3)
    assert r3.status_code == 201, r3.get_json()
    cleanup.order_ids.append(r3.get_json()["order"]["id"])

    final = db.products.find_one({"_id": pid})
    assert final["stock"] == 0
    assert final["status"] == "out"

    p4 = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(p4["customer"]["email"])
    r4 = client.post("/api/orders", json=p4)
    assert r4.status_code == 400
    assert db.products.find_one({"_id": pid})["stock"] == 0  # never negative


# ---------------------------------------------------------------------
# Partial shortage: cart qty exceeds current stock -> rejected, no oversell
# ---------------------------------------------------------------------
def test_partial_shortage_rejected_no_oversell(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 9
    make_product(db, pid, stock=3)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 5}])
    cleanup.customer_emails.append(payload["customer"]["email"])
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 400
    assert db.products.find_one({"_id": pid})["stock"] == 3  # unchanged, never negative


# ---------------------------------------------------------------------
# TEST 10 from the spec: two simultaneous orders for the last unit(s) ->
# exactly the available stock is sold, never oversold, never negative.
# ---------------------------------------------------------------------
def test_barcode_lookup_finds_by_barcode_then_sku(admin_client, client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 11
    make_product(db, pid, stock=5, sku=f"TEST-{pid}")
    db.products.update_one({"_id": pid}, {"$set": {"barcode": "7290000000099"}})
    cleanup.product_ids.append(pid)

    assert client.get("/api/products/lookup?code=7290000000099").status_code == 401

    by_barcode = admin_client.get("/api/products/lookup?code=7290000000099")
    assert by_barcode.status_code == 200, by_barcode.get_json()
    assert by_barcode.get_json()["id"] == pid

    by_sku = admin_client.get(f"/api/products/lookup?code=TEST-{pid}")
    assert by_sku.status_code == 200
    assert by_sku.get_json()["id"] == pid

    not_found = admin_client.get("/api/products/lookup?code=DOES-NOT-EXIST")
    assert not_found.status_code == 404


# ---------------------------------------------------------------------
# Regression: products.barcode has a unique+sparse index. A sparse index
# only excludes a document MISSING the field — a document with an explicit
# barcode:null is still indexed, so naively defaulting a missing barcode to
# null broke every second product creation (see backend/services/products_service.py).
# ---------------------------------------------------------------------
def test_two_products_without_barcode_can_both_be_created(admin_client, db, cleanup):
    payload = lambda pid: {
        "sku": f"TEST-{pid}", "cat": "gifts", "catLabel": "מתנות", "name": f"מוצר {pid}",
        "price": 10, "stock": 1, "threshold": 1,
    }
    pid1, pid2 = TEST_PRODUCT_ID_START + 12, TEST_PRODUCT_ID_START + 13
    r1 = admin_client.post("/api/products", json=payload(pid1))
    assert r1.status_code == 201, r1.get_json()
    cleanup.product_ids.append(r1.get_json()["id"])
    assert "barcode" not in r1.get_json() or r1.get_json()["barcode"] is None

    r2 = admin_client.post("/api/products", json=payload(pid2))
    assert r2.status_code == 201, r2.get_json()  # this is the line that used to 500 with a DuplicateKeyError
    cleanup.product_ids.append(r2.get_json()["id"])


def test_duplicate_barcode_rejected_with_clean_error_not_500(admin_client, db, cleanup):
    pid1, pid2 = TEST_PRODUCT_ID_START + 14, TEST_PRODUCT_ID_START + 15
    r1 = admin_client.post("/api/products", json={
        "sku": f"TEST-{pid1}", "cat": "gifts", "catLabel": "מתנות", "name": "מוצר א",
        "price": 10, "stock": 1, "threshold": 1, "barcode": "9999888877",
    })
    assert r1.status_code == 201, r1.get_json()
    cleanup.product_ids.append(r1.get_json()["id"])

    r2 = admin_client.post("/api/products", json={
        "sku": f"TEST-{pid2}", "cat": "gifts", "catLabel": "מתנות", "name": "מוצר ב",
        "price": 10, "stock": 1, "threshold": 1, "barcode": "9999888877",
    })
    assert r2.status_code == 400, r2.get_json()
    assert "ברקוד" in r2.get_json()["error"]


def test_clearing_a_barcode_does_not_block_future_barcode_less_creates(admin_client, db, cleanup):
    pid1, pid2 = TEST_PRODUCT_ID_START + 16, TEST_PRODUCT_ID_START + 17
    r1 = admin_client.post("/api/products", json={
        "sku": f"TEST-{pid1}", "cat": "gifts", "catLabel": "מתנות", "name": "מוצר עם ברקוד",
        "price": 10, "stock": 1, "threshold": 1, "barcode": "5551112223",
    })
    assert r1.status_code == 201, r1.get_json()
    created_id = r1.get_json()["id"]
    cleanup.product_ids.append(created_id)

    clear = admin_client.put(f"/api/products/{created_id}", json={"barcode": ""})
    assert clear.status_code == 200, clear.get_json()
    assert db.products.find_one({"_id": created_id}).get("barcode") is None
    assert "barcode" not in db.products.find_one({"_id": created_id})

    r2 = admin_client.post("/api/products", json={
        "sku": f"TEST-{pid2}", "cat": "gifts", "catLabel": "מתנות", "name": "מוצר בלי ברקוד",
        "price": 10, "stock": 1, "threshold": 1,
    })
    assert r2.status_code == 201, r2.get_json()  # must not collide with the just-cleared product
    cleanup.product_ids.append(r2.get_json()["id"])


def test_concurrent_orders_never_oversell_or_go_negative(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 10
    make_product(db, pid, stock=1)
    cleanup.product_ids.append(pid)

    results = []
    emails = [unique_email(), unique_email()]
    cleanup.customer_emails.extend(emails)

    def place_order(email):
        with flask_app.test_client() as c:
            payload = checkout_payload([{"productId": pid, "qty": 1}], email=email)
            r = c.post("/api/orders", json=payload)
            results.append(r)

    threads = [threading.Thread(target=place_order, args=(e,)) for e in emails]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for r in results:
        if r.status_code == 201:
            cleanup.order_ids.append(r.get_json()["order"]["id"])

    statuses = sorted(r.status_code for r in results)
    assert statuses == [201, 400], f"expected exactly one success and one rejection, got {statuses}"

    final = db.products.find_one({"_id": pid})
    assert final["stock"] == 0  # never negative, never both succeeded
    assert final["status"] == "out"
