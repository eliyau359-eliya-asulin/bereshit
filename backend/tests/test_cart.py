"""Phase D: server-side cart for authenticated customers — isolation
between customers (IDOR), and basic shape validation.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


def unique_email():
    return f"qa-cart.{uuid.uuid4().hex[:10]}@example.com"


def register(email, name="לקוחת עגלה"):
    c = flask_app.test_client()
    res = c.post("/api/auth/customer/register", json={
        "name": name, "email": email, "phone": "050-1112222", "password": "SuperSecret123",
    })
    assert res.status_code == 201, res.get_json()
    return c, res.get_json()["customer"]["id"]


def test_cart_requires_authentication(client, db):
    assert client.get("/api/cart").status_code == 401
    assert client.put("/api/cart", json={"items": []}).status_code == 401


def test_customer_can_save_and_fetch_own_cart(db):
    email = unique_email()
    c, cid = register(email)
    try:
        put_res = c.put("/api/cart", json={"items": [{"productId": 1, "qty": 2}, {"productId": 3, "qty": 1}]})
        assert put_res.status_code == 200, put_res.get_json()

        get_res = c.get("/api/cart")
        assert get_res.status_code == 200
        items = {i["productId"]: i["qty"] for i in get_res.get_json()["items"]}
        assert items == {1: 2, 3: 1}
    finally:
        db.customers.delete_one({"email": email})
        db.carts.delete_one({"_id": cid})


def test_duplicate_product_ids_in_one_payload_are_combined(db):
    email = unique_email()
    c, cid = register(email)
    try:
        res = c.put("/api/cart", json={"items": [{"productId": 5, "qty": 2}, {"productId": 5, "qty": 3}]})
        assert res.status_code == 200
        items = {i["productId"]: i["qty"] for i in res.get_json()["items"]}
        assert items == {5: 5}
    finally:
        db.customers.delete_one({"email": email})
        db.carts.delete_one({"_id": cid})


def test_customer_cannot_see_another_customers_cart(db):
    email_a = unique_email()
    email_b = unique_email()
    client_a, cid_a = register(email_a, "לקוחה א")
    client_b, cid_b = register(email_b, "לקוחה ב")
    try:
        client_a.put("/api/cart", json={"items": [{"productId": 99, "qty": 4}]})

        # B never called PUT — B's cart must be empty, never A's items.
        res_b = client_b.get("/api/cart")
        assert res_b.status_code == 200
        assert res_b.get_json()["items"] == []
    finally:
        db.customers.delete_one({"email": email_a})
        db.customers.delete_one({"email": email_b})
        db.carts.delete_many({"_id": {"$in": [cid_a, cid_b]}})


def test_invalid_cart_entries_are_dropped_not_500ed(db):
    email = unique_email()
    c, cid = register(email)
    try:
        res = c.put("/api/cart", json={"items": [
            {"productId": 1, "qty": 2},
            {"productId": "not-an-int", "qty": 1},
            {"productId": 2, "qty": -5},
            {"productId": 3},
            "garbage",
        ]})
        assert res.status_code == 200, res.get_json()
        items = {i["productId"]: i["qty"] for i in res.get_json()["items"]}
        assert items == {1: 2}
    finally:
        db.customers.delete_one({"email": email})
        db.carts.delete_one({"_id": cid})
