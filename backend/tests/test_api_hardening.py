"""Phase C: pagination and the inventory-log endpoint. Existing list
endpoints must keep returning a bare array when no page param is given
(backward compatibility with the current admin/customer frontends) and
switch to a paginated envelope only when explicitly asked.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db

TEST_PRODUCT_ID_START = 930001


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


def unique_email():
    return f"qa-hardening.{uuid.uuid4().hex[:10]}@example.com"


def make_product(db, pid, stock=10, price=50, sku=None):
    doc = {
        "_id": pid, "sku": sku or f"TEST-{pid}", "cat": "gifts", "catLabel": "מתנות",
        "name": f"מוצר בדיקה {pid}", "price": price, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": stock, "threshold": 2, "status": "active", "sold": 0, "image": None,
    }
    db.products.delete_one({"_id": pid})
    db.products.insert_one(doc)
    return doc


def test_orders_list_stays_a_bare_array_without_page_param(admin_client, db):
    res = admin_client.get("/api/orders")
    assert res.status_code == 200
    assert isinstance(res.get_json(), list)


def test_orders_list_paginates_when_page_param_given(admin_client, db):
    res = admin_client.get("/api/orders?page=1&pageSize=2")
    assert res.status_code == 200
    body = res.get_json()
    assert isinstance(body, dict)
    assert set(["items", "total", "page", "pageSize"]).issubset(body.keys())
    assert len(body["items"]) <= 2
    assert body["page"] == 1
    assert body["pageSize"] == 2


def test_customers_list_paginates_when_page_param_given(admin_client, db):
    res = admin_client.get("/api/customers?page=1&pageSize=3")
    assert res.status_code == 200
    body = res.get_json()
    assert isinstance(body, dict)
    assert len(body["items"]) <= 3
    assert all("passwordHash" not in c for c in body["items"])


def test_inventory_log_endpoint_requires_admin_and_paginates(client, admin_client, db):
    pid = TEST_PRODUCT_ID_START + 1
    make_product(db, pid, stock=20)
    try:
        admin_client.put(f"/api/products/{pid}", json={"stock": 15, "reason": "בדיקה"})
        admin_client.put(f"/api/products/{pid}", json={"stock": 10, "reason": "בדיקה 2"})

        anon = client.get(f"/api/products/inventory-log?productId={pid}")
        assert anon.status_code == 401

        res = admin_client.get(f"/api/products/inventory-log?productId={pid}&page=1&pageSize=1")
        assert res.status_code == 200
        body = res.get_json()
        assert body["total"] == 2
        assert len(body["items"]) == 1
        assert body["items"][0]["productId"] == pid
    finally:
        db.products.delete_one({"_id": pid})
        db.inventory_log.delete_many({"productId": pid})


def test_oversized_request_body_rejected(client):
    # Use a public (unauthenticated) endpoint so the size limit is what's
    # actually being tested, not an auth check short-circuiting first.
    # The global cap is 9MB (sized for image uploads); a JSON body has no
    # business ever approaching that, so 10MB must still be refused.
    huge = "x" * (10 * 1024 * 1024)
    res = client.post("/api/orders", data='{"notes":"' + huge + '"}', content_type="application/json")
    assert res.status_code == 413
