"""Shared fixtures for the backend test suite. `client`/`db`/`cleanup` stay
defined locally in each test file (unchanged, to avoid touching working
tests unnecessarily) — this file only adds fixtures that didn't exist
before authentication did: authenticated admin/customer test clients.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, for `import backend...`

from backend.app import app as flask_app
from backend.db.mongo import get_db
from backend.auth.security import hash_password
from backend.auth.roles import SUPER_ADMIN

TEST_ADMIN_ID = "AU-TEST-SUPER-ADMIN"
TEST_ADMIN_EMAIL = "test-super-admin@bereshit.test"
TEST_ADMIN_PASSWORD = "TestSuperAdmin123!"


@pytest.fixture()
def admin_client():
    """A Flask test client already logged in as a super_admin. The test
    client keeps its own cookie jar, so every subsequent request made
    through this object carries the session cookie automatically — no
    need to pass it manually."""
    flask_app.testing = True
    db = get_db()
    # The login endpoint is IP+account rate-limited (by design — see
    # backend/auth/rate_limit.py). Every test run's admin_client fixture
    # logs in from the same test-client "IP", so repeated full-suite runs
    # in one session would otherwise accumulate attempts against the same
    # counter and eventually lock this fixture itself out with a 429 —
    # clearing it here keeps the test suite from ever self-throttling.
    db.login_attempts.delete_many({"_id": {"$regex": TEST_ADMIN_EMAIL}})
    db.login_attempts.delete_many({"_id": {"$regex": "^ip:admin:"}})
    db.admin_users.delete_one({"_id": TEST_ADMIN_ID})
    db.admin_users.insert_one({
        "_id": TEST_ADMIN_ID,
        "name": "Test Super Admin",
        "email": TEST_ADMIN_EMAIL,
        "passwordHash": hash_password(TEST_ADMIN_PASSWORD),
        "role": SUPER_ADMIN,
        "active": True,
    })
    c = flask_app.test_client()
    res = c.post("/api/auth/admin/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD})
    assert res.status_code == 200, res.get_json()
    yield c
    c.post("/api/auth/admin/logout")
    db.admin_users.delete_one({"_id": TEST_ADMIN_ID})


def make_customer_client(db, email, password="TestCustomer123!", name="Test Customer", phone="050-0000000"):
    """Registers (or reuses) a customer account and returns a logged-in
    test client for it, for tests that need a real authenticated-customer
    checkout/order-history flow."""
    flask_app.testing = True
    c = flask_app.test_client()
    res = c.post("/api/auth/customer/register", json={
        "name": name, "email": email, "phone": phone, "password": password,
    })
    assert res.status_code in (200, 201), res.get_json()
    return c
