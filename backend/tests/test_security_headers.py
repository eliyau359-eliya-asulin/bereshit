"""Security headers (CSP + friends) on every API response, and a couple
of end-to-end checks that untrusted product data round-trips through the
API as plain JSON — never as something a browser could interpret as HTML
on its own. The actual XSS defense for the storefront/admin UI lives in
the frontend rendering layer (escaped output at the DOM boundary); what
this file verifies is the backend half of that contract: the API never
serves attacker-controlled content with a content type or header set that
would let a browser execute it directly.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db

TEST_PRODUCT_ID_START = 950001


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


def test_api_responses_carry_the_expected_security_headers(client):
    res = client.get("/api/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = res.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    # unsafe-eval must never be present — no part of this app needs eval/Function.
    assert "unsafe-eval" not in csp


def test_csp_allows_the_blob_image_host_and_google_fonts_only(client):
    csp = client.get("/api/health").headers.get("Content-Security-Policy")
    assert "https://*.public.blob.vercel-storage.com" in csp
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp


def test_csp_connect_src_allows_exactly_the_hosts_the_direct_blob_upload_needs(client):
    """The Admin's browser PUTs a product photo directly to Vercel Blob
    using a presigned URL (see api/blob-upload-token.js). That URL's
    origin comes from wherever @vercel/blob's presignUrl() actually
    targets — confirmed by inspecting the pinned package's compiled
    source (not documented at the wire-protocol level) to be
    https://vercel.com/api/blob by default, not the CDN read host. A CSP
    that only allowed the CDN host silently blocked every direct upload
    with no server-side trace at all (the browser never sends the
    request) — this is the regression test for that incident."""
    csp = client.get("/api/health").headers.get("Content-Security-Policy")
    connect_src = next(part for part in csp.split(";") if part.strip().startswith("connect-src"))
    assert "'self'" in connect_src
    assert "https://blob.vercel-storage.com" in connect_src
    assert "https://vercel.com" in connect_src
    # Bounded to these specific origins — never a wildcard.
    assert "*" not in connect_src


def test_product_api_response_is_json_not_html_even_with_script_tag_in_name(db):
    """A product name containing a <script> tag must come back as an
    inert JSON string value — Flask's jsonify() always sets
    Content-Type: application/json, so even navigating directly to this
    endpoint can never make a browser render the payload as HTML."""
    from backend.services.products_service import create_product, delete_product

    sku = f"HEADER-XSS-{TEST_PRODUCT_ID_START}"
    db.products.delete_many({"sku": sku})
    payload_name = '<script>alert(document.cookie)</script>'
    created = create_product({
        "sku": sku, "cat": "gifts", "catLabel": "מתנות", "name": payload_name,
        "price": 10, "stock": 1, "threshold": 1,
    })
    try:
        flask_app.testing = True
        c = flask_app.test_client()
        res = c.get(f"/api/products/{created['id']}")
        assert res.status_code == 200
        assert res.mimetype == "application/json"
        assert res.get_json()["name"] == payload_name
    finally:
        delete_product(created["id"])
