"""Integration tests for Phase B: admin authentication/authorization and
customer authentication + IDOR protection. Same pattern as the other
test files — runs against the real configured MongoDB, cleans up after
itself, uses a dedicated id/email range.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db
from backend.auth.security import hash_password
from backend.auth.roles import INVENTORY_MANAGER

TEST_PRODUCT_ID_START = 920001


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
        self.admin_ids = []

    def sweep(self):
        if self.product_ids:
            self.db.products.delete_many({"_id": {"$in": self.product_ids}})
            self.db.inventory_log.delete_many({"productId": {"$in": self.product_ids}})
        if self.customer_emails:
            self.db.customers.delete_many({"email": {"$in": self.customer_emails}})
        if self.order_ids:
            self.db.orders.delete_many({"_id": {"$in": self.order_ids}})
        if self.admin_ids:
            self.db.admin_users.delete_many({"_id": {"$in": self.admin_ids}})


@pytest.fixture()
def cleanup(db):
    c = Cleanup(db)
    yield c
    c.sweep()


def make_product(db, pid, stock=10, price=100, sku=None):
    doc = {
        "_id": pid, "sku": sku or f"TEST-{pid}", "cat": "gifts", "catLabel": "מתנות",
        "name": f"מוצר בדיקה {pid}", "price": price, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": stock, "threshold": 2, "status": "active", "sold": 0, "image": None,
    }
    db.products.delete_one({"_id": pid})
    db.products.insert_one(doc)
    return doc


def unique_email(prefix="qa-auth"):
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


def checkout_payload(items, email=None, name="בדיקה אוטומטית", phone="050-0000000"):
    return {
        "customer": {"name": name, "email": email or unique_email(), "phone": phone},
        "shipping": {"method": "standard", "address": "רחוב הבדיקה 1", "city": "תל אביב", "zip": "6100000"},
        "items": items,
        "payment": {"method": "cash_on_delivery"},
    }


# ---------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------

def test_admin_write_endpoints_reject_unauthenticated_requests(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 1
    make_product(db, pid)
    cleanup.product_ids.append(pid)

    assert client.post("/api/products", json={"sku": "X", "cat": "gifts", "catLabel": "מ", "name": "n", "price": 1, "stock": 1, "threshold": 1}).status_code == 401
    assert client.put(f"/api/products/{pid}", json={"stock": 5}).status_code == 401
    assert client.delete(f"/api/products/{pid}").status_code == 401
    assert client.get("/api/customers").status_code == 401
    assert client.put(f"/api/orders/BJ-1", json={"status": "בטיפול"}).status_code == 401


def test_admin_login_wrong_password_rejected_and_no_session_created(client, db, cleanup):
    admin_id = "AU-TEST-WRONGPW"
    cleanup.admin_ids.append(admin_id)
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "T", "email": unique_email("admin"),
        "passwordHash": hash_password("CorrectHorse123!"), "role": "admin", "active": True,
    })
    email = db.admin_users.find_one({"_id": admin_id})["email"]

    res = client.post("/api/auth/admin/login", json={"email": email, "password": "WrongPassword!"})
    assert res.status_code == 401
    assert "bereshit_admin_session" not in res.headers.get("Set-Cookie", "")


def test_admin_login_logout_cycle(client, db, cleanup):
    admin_id = "AU-TEST-CYCLE"
    cleanup.admin_ids.append(admin_id)
    email = unique_email("admin")
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "T", "email": email,
        "passwordHash": hash_password("CorrectHorse123!"), "role": "admin", "active": True,
    })

    res = client.post("/api/auth/admin/login", json={"email": email, "password": "CorrectHorse123!"})
    assert res.status_code == 200, res.get_json()

    me = client.get("/api/auth/admin/me")
    assert me.status_code == 200
    assert me.get_json()["admin"]["id"] == admin_id

    logout = client.post("/api/auth/admin/logout")
    assert logout.status_code == 200

    me_after = client.get("/api/auth/admin/me")
    assert me_after.status_code == 401


def test_inventory_manager_role_cannot_delete_product_but_can_adjust_stock(client, db, cleanup):
    admin_id = "AU-TEST-INVMGR"
    cleanup.admin_ids.append(admin_id)
    email = unique_email("invmgr")
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "Inv", "email": email,
        "passwordHash": hash_password("CorrectHorse123!"), "role": INVENTORY_MANAGER, "active": True,
    })
    login = client.post("/api/auth/admin/login", json={"email": email, "password": "CorrectHorse123!"})
    assert login.status_code == 200

    pid = TEST_PRODUCT_ID_START + 2
    make_product(db, pid, stock=10)
    cleanup.product_ids.append(pid)

    # Allowed: stock-only adjustment.
    stock_res = client.put(f"/api/products/{pid}", json={"stock": 7, "reason": "ספירת מלאי"})
    assert stock_res.status_code == 200, stock_res.get_json()

    # Forbidden: full product edit (non-stock field) and delete.
    edit_res = client.put(f"/api/products/{pid}", json={"name": "שם חדש"})
    assert edit_res.status_code == 403

    delete_res = client.delete(f"/api/products/{pid}")
    assert delete_res.status_code == 403


def test_deactivated_admin_session_is_revoked_immediately(admin_client, client, db, cleanup):
    admin_id = "AU-TEST-DEACT"
    cleanup.admin_ids.append(admin_id)
    email = unique_email("deact")
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "D", "email": email,
        "passwordHash": hash_password("CorrectHorse123!"), "role": "admin", "active": True,
    })
    victim = flask_app.test_client()
    login = victim.post("/api/auth/admin/login", json={"email": email, "password": "CorrectHorse123!"})
    assert login.status_code == 200
    assert victim.get("/api/auth/admin/me").status_code == 200

    # A super_admin deactivates that account...
    deact = admin_client.put(f"/api/admin/users/{admin_id}", json={"active": False})
    assert deact.status_code == 200, deact.get_json()

    # ...and the already-logged-in session is dead immediately, not just future logins.
    assert victim.get("/api/auth/admin/me").status_code == 401


# ---------------------------------------------------------------------
# Customer auth + IDOR
# ---------------------------------------------------------------------

def test_customer_register_login_logout_cycle(client, db, cleanup):
    email = unique_email("cust")
    cleanup.customer_emails.append(email)

    reg = client.post("/api/auth/customer/register", json={
        "name": "לקוח בדיקה", "email": email, "phone": "050-1234567", "password": "SuperSecret123",
    })
    assert reg.status_code == 201, reg.get_json()

    me = client.get("/api/auth/customer/me")
    assert me.status_code == 200
    assert me.get_json()["customer"]["email"] == email
    assert "passwordHash" not in me.get_json()["customer"]

    client.post("/api/auth/customer/logout")
    assert client.get("/api/auth/customer/me").status_code == 401

    login = client.post("/api/auth/customer/login", json={"email": email, "password": "SuperSecret123"})
    assert login.status_code == 200
    assert client.get("/api/auth/customer/me").status_code == 200


def test_customer_login_wrong_password_rejected(client, db, cleanup):
    email = unique_email("cust")
    cleanup.customer_emails.append(email)
    client.post("/api/auth/customer/register", json={
        "name": "לקוח", "email": email, "phone": "050-1234567", "password": "SuperSecret123",
    })
    client.post("/api/auth/customer/logout")

    res = client.post("/api/auth/customer/login", json={"email": email, "password": "WrongOne123"})
    assert res.status_code == 401


def test_customer_cannot_view_another_customers_order(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 3
    make_product(db, pid, stock=10, price=80)
    cleanup.product_ids.append(pid)

    # Customer A checks out as a guest.
    payload_a = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(payload_a["customer"]["email"])
    order_a = client.post("/api/orders", json=payload_a)
    assert order_a.status_code == 201, order_a.get_json()
    order_id = order_a.get_json()["order"]["id"]
    cleanup.order_ids.append(order_id)

    # Customer B registers a real account and tries to fetch A's order by id.
    email_b = unique_email("custb")
    cleanup.customer_emails.append(email_b)
    client_b = flask_app.test_client()
    reg_b = client_b.post("/api/auth/customer/register", json={
        "name": "לקוח ב", "email": email_b, "phone": "050-7654321", "password": "SuperSecret123",
    })
    assert reg_b.status_code == 201

    forbidden = client_b.get(f"/api/orders/{order_id}")
    assert forbidden.status_code == 404  # same response as "doesn't exist" — no existence leak

    list_res = client_b.get("/api/orders")
    assert list_res.status_code == 200
    assert all(o["id"] != order_id for o in list_res.get_json())


def test_authenticated_checkout_ignores_client_supplied_email_for_attribution(client, db, cleanup):
    """A logged-in customer cannot attribute an order to a different
    account by editing the `customer.email` field in the checkout payload
    — the server always uses the session's real account."""
    email = unique_email("realacct")
    other_email = unique_email("spoofed")
    cleanup.customer_emails += [email, other_email]

    reg = client.post("/api/auth/customer/register", json={
        "name": "בעל החשבון", "email": email, "phone": "050-1112222", "password": "SuperSecret123",
    })
    assert reg.status_code == 201
    account_id = reg.get_json()["customer"]["id"]

    pid = TEST_PRODUCT_ID_START + 4
    make_product(db, pid, stock=10, price=55)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 1}], email=other_email)
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    order_id = res.get_json()["order"]["id"]
    cleanup.order_ids.append(order_id)

    assert res.get_json()["order"]["customerId"] == account_id
    assert db.customers.find_one({"email": other_email}) is None  # no account was ever created for the spoofed email


def test_repeated_failed_admin_logins_are_rate_limited(client, db, cleanup):
    # Wipe the whole collection first — the IP-based counter is shared
    # across every admin login attempt made by this test process (real
    # Mongo, no per-test isolation for it), so a prior test run's
    # not-yet-expired counters could otherwise cause a false lockout here
    # or leave this test's lockout bleeding into unrelated tests.
    db.login_attempts.delete_many({})

    admin_id = "AU-TEST-RATELIMIT"
    cleanup.admin_ids.append(admin_id)
    email = unique_email("ratelimit")
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "R", "email": email,
        "passwordHash": hash_password("CorrectHorse123!"), "role": "admin", "active": True,
    })

    last_status = None
    for _ in range(9):
        res = client.post("/api/auth/admin/login", json={"email": email, "password": "WrongPassword!"})
        last_status = res.status_code
    assert last_status == 429, f"expected lockout after repeated failures, got {last_status}"

    # Even the CORRECT password is refused while locked out.
    res = client.post("/api/auth/admin/login", json={"email": email, "password": "CorrectHorse123!"})
    assert res.status_code == 429

    db.login_attempts.delete_many({})


def test_guest_checkout_still_works_without_any_session(client, db, cleanup):
    pid = TEST_PRODUCT_ID_START + 5
    make_product(db, pid, stock=5, price=30)
    cleanup.product_ids.append(pid)

    payload = checkout_payload([{"productId": pid, "qty": 1}])
    cleanup.customer_emails.append(payload["customer"]["email"])
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 201, res.get_json()
    cleanup.order_ids.append(res.get_json()["order"]["id"])
