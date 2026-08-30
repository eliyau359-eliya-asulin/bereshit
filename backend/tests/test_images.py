"""Phase H: image validation/processing, and the image routes' auth +
business-rule behavior.

The Admin upload flow is a client-direct-upload: the browser PUTs the raw
file straight to Vercel Blob using a short-lived credential minted by a
separate Node function (api/blob-upload-token.js, not exercised by this
Python test suite — see its own header comment for what it does and why),
then tells Flask where it landed via POST /api/images/process. That
route, plus GET /api/images/upload-authorize (the server-to-server
auth/permission check the Node function calls before minting anything),
are what's tested here.

There is no real Blob store configured in this test environment (no
BLOB_* credentials are available here), so several of these naturally
exercise the "storage not configured" path — itself a real, important
behavior to verify (a clear 503, never a silent fake success). The pure
validation/resize logic in backend/images/processing.py needs no store
at all and is covered thoroughly here; the Blob-interaction tests mock
`requests`/`storage` so they run without real credentials.
"""
import io
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db
from backend.images.processing import validate_and_process, MAIN_MAX_EDGE, THUMB_MAX_EDGE
from backend.models.schemas import ValidationError


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


def make_image_bytes(width, height, fmt="PNG", color=(200, 50, 50)):
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------
# Pure validation/processing logic
# ---------------------------------------------------------------------

def test_valid_png_is_accepted_and_converted_to_webp():
    result = validate_and_process(make_image_bytes(500, 500, "PNG"))
    assert result["content_type"] == "image/webp"
    assert result["width"] == 500 and result["height"] == 500
    assert result["main_bytes"][:4] != b"\x89PNG"  # actually re-encoded, not just relabeled


def test_valid_jpeg_is_accepted():
    result = validate_and_process(make_image_bytes(300, 400, "JPEG"))
    assert result["width"] == 300 and result["height"] == 400


def test_large_image_is_downscaled_to_max_edge():
    result = validate_and_process(make_image_bytes(4000, 2000, "PNG"))
    assert max(result["width"], result["height"]) == MAIN_MAX_EDGE
    assert result["width"] / result["height"] == pytest.approx(2.0, rel=0.02)  # aspect ratio preserved


def test_small_image_is_not_upscaled():
    result = validate_and_process(make_image_bytes(120, 120, "PNG"))
    assert result["width"] == 120 and result["height"] == 120


def test_thumbnail_generation_via_upload_service_shrinks_further(monkeypatch):
    # validate_and_process itself only returns the main-sized bytes/thumb
    # bytes; verify the thumb is actually smaller by decoding it back.
    result = validate_and_process(make_image_bytes(2000, 1000, "PNG"))
    thumb = Image.open(io.BytesIO(result["thumb_bytes"]))
    assert max(thumb.size) == THUMB_MAX_EDGE


def test_non_image_bytes_rejected():
    with pytest.raises(ValidationError):
        validate_and_process(b"this is not an image, just plain text bytes")


def test_disallowed_format_rejected():
    img = Image.new("RGB", (200, 200), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    with pytest.raises(ValidationError):
        validate_and_process(buf.getvalue())


def test_tiny_image_rejected():
    with pytest.raises(ValidationError):
        validate_and_process(make_image_bytes(10, 10, "PNG"))


def test_oversized_source_file_rejected():
    from backend.images import processing
    with pytest.raises(ValidationError):
        validate_and_process(b"x" * (processing.MAX_SOURCE_BYTES + 1))


def test_empty_bytes_rejected():
    with pytest.raises(ValidationError):
        validate_and_process(b"")


# ---------------------------------------------------------------------
# Route auth + behavior for the client-direct-upload flow:
#   GET  /api/images/upload-authorize  (called server-to-server by the
#        Node upload-token function, never directly by the browser)
#   POST /api/images/process           (fetches the client's already-
#        staged upload back from Blob and runs the real pipeline on it)
# No real bucket is configured in this test environment (no BLOB_*
# credentials are available here), so most of these naturally exercise
# the "storage not configured" path — itself a real, important behavior
# to verify (a clear 503, never a silent fake success).
# ---------------------------------------------------------------------

VALID_STAGING_PATHNAME = "staging/" + "a" * 32 + ".upload"


def test_upload_authorize_requires_admin_auth(client):
    res = client.get("/api/images/upload-authorize")
    assert res.status_code == 401


def test_upload_authorize_returns_ok_for_authorized_admin(admin_client):
    res = admin_client.get("/api/images/upload-authorize")
    assert res.status_code == 200
    assert res.get_json() == {"authorized": True}


def test_process_requires_admin_auth(client):
    res = client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 401


def test_process_rejects_malformed_pathname_before_touching_storage(admin_client):
    """A pathname outside the `staging/<uuid>.upload` shape (e.g. an
    attempt to point this at an arbitrary existing product key, or a
    path-traversal-looking value) is rejected outright — this endpoint
    must never be usable to "reprocess" anything other than a file this
    exact flow just staged."""
    for bad in ["products/existing-product-image.webp", "staging/../../secrets.txt",
                "staging/not-a-uuid.upload", "javascript:alert(1)", ""]:
        res = admin_client.post("/api/images/process", json={"pathname": bad})
        assert res.status_code == 400, bad


def test_process_without_storage_configured_returns_503_not_a_fake_success(admin_client):
    # This test environment has no BERESHIT_IMAGES_STORE_ID/
    # BERESHIT_IMAGES_READ_WRITE_TOKEN configured — the route must say so
    # clearly, never pretend it worked.
    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 503
    assert res.get_json()["code"] == "STORAGE_NOT_CONFIGURED"


def test_process_rejects_invalid_staged_image_and_still_cleans_up(admin_client, monkeypatch):
    from backend.services import images_service

    delete_calls = []
    monkeypatch.setattr(images_service.storage, "fetch_bytes", lambda key: b"not a real image")
    monkeypatch.setattr(images_service.storage, "public_url_for_key", lambda key: f"{TEST_BLOB_URL_PREFIX}/{key}")
    monkeypatch.setattr(images_service.storage, "delete_object", lambda url: delete_calls.append(url))

    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 400
    # The garbage staging blob must never be left behind just because it
    # failed validation.
    assert delete_calls == [f"{TEST_BLOB_URL_PREFIX}/{VALID_STAGING_PATHNAME}"]


def test_process_never_leaks_blob_credentials_in_any_response(admin_client, monkeypatch):
    """Regression guard for the client-direct-upload architecture: no
    Flask JSON response — success or error — may ever contain the real
    BERESHIT_IMAGES_READ_WRITE_TOKEN value, regardless of what triggers
    the response."""
    monkeypatch.setenv("BERESHIT_IMAGES_READ_WRITE_TOKEN", "super-secret-rw-token-must-never-leak")
    for bad in ["", "not/staging/shape"]:
        res = admin_client.post("/api/images/process", json={"pathname": bad})
        assert "super-secret-rw-token-must-never-leak" not in res.get_data(as_text=True)
    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert "super-secret-rw-token-must-never-leak" not in res.get_data(as_text=True)
    res = admin_client.get("/api/images/upload-authorize")
    assert "super-secret-rw-token-must-never-leak" not in res.get_data(as_text=True)


def test_process_full_flow_fetches_stages_and_uploads_then_cleans_up(admin_client, monkeypatch):
    """End-to-end (within this process): a valid staged image is fetched
    back from Blob, validated/resized/WebP-converted, uploaded as a real
    product main+thumbnail, and the staging blob is deleted — the
    complete replacement for the old direct-multipart-upload endpoint."""
    from backend.services import images_service

    put_calls = []
    delete_calls = []

    def fake_fetch_bytes(key):
        assert key == VALID_STAGING_PATHNAME
        return make_image_bytes(500, 500, "PNG")

    def fake_upload_bytes(data, key, content_type):
        put_calls.append(key)
        return f"{TEST_BLOB_URL_PREFIX}/{key}"

    monkeypatch.setattr(images_service.storage, "is_configured", lambda: True)
    monkeypatch.setattr(images_service.storage, "fetch_bytes", fake_fetch_bytes)
    monkeypatch.setattr(images_service.storage, "public_url_for_key", lambda key: f"{TEST_BLOB_URL_PREFIX}/{key}")
    monkeypatch.setattr(images_service.storage, "upload_bytes", fake_upload_bytes)
    monkeypatch.setattr(images_service.storage, "delete_object", lambda url: delete_calls.append(url))

    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["url"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/")
    assert body["thumbnailUrl"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/thumbs/")
    assert body["width"] == 500 and body["height"] == 500
    assert len(put_calls) == 2  # main + thumbnail
    # The temporary staging blob (not the new product images) was cleaned up.
    assert delete_calls == [f"{TEST_BLOB_URL_PREFIX}/{VALID_STAGING_PATHNAME}"]


# ---------------------------------------------------------------------
# Regression: production incident — a malformed staging-blob cleanup
# delete() must never mask an otherwise-successful upload. Before this
# fix, a failure here (exactly what "Vercel Blob delete failed (400):
# Some urls are malformed" was) propagated out of process_staged_image
# and made the *entire* upload fail even though the real product
# image/thumbnail had already been created successfully.
# ---------------------------------------------------------------------

def test_process_succeeds_even_when_staging_cleanup_delete_fails(admin_client, monkeypatch):
    from backend.services import images_service

    def fake_fetch_bytes(key):
        return make_image_bytes(400, 400, "PNG")

    def fake_upload_bytes(data, key, content_type):
        return f"{TEST_BLOB_URL_PREFIX}/{key}"

    def failing_delete(url):
        raise RuntimeError("Vercel Blob delete failed (400): {\"error\":{\"code\":\"bad_request\",\"message\":\"Some urls are malformed\"}}")

    monkeypatch.setattr(images_service.storage, "is_configured", lambda: True)
    monkeypatch.setattr(images_service.storage, "fetch_bytes", fake_fetch_bytes)
    monkeypatch.setattr(images_service.storage, "public_url_for_key", lambda key: f"{TEST_BLOB_URL_PREFIX}/{key}")
    monkeypatch.setattr(images_service.storage, "upload_bytes", fake_upload_bytes)
    monkeypatch.setattr(images_service.storage, "delete_object", failing_delete)

    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["url"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/")
    assert body["thumbnailUrl"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/thumbs/")


def test_process_still_rejects_invalid_image_when_cleanup_delete_also_fails(admin_client, monkeypatch):
    """Cleanup is best-effort in both directions: a delete failure must
    not turn a genuine validation failure into a fake success either."""
    from backend.services import images_service

    monkeypatch.setattr(images_service.storage, "fetch_bytes", lambda key: b"not a real image")
    monkeypatch.setattr(images_service.storage, "public_url_for_key", lambda key: f"{TEST_BLOB_URL_PREFIX}/{key}")
    monkeypatch.setattr(images_service.storage, "delete_object", lambda url: (_ for _ in ()).throw(RuntimeError("delete also failed")))

    res = admin_client.post("/api/images/process", json={"pathname": VALID_STAGING_PATHNAME})
    assert res.status_code == 400


def test_delete_requires_admin_auth(client):
    res = client.delete("/api/images", json={"url": "https://example.com/products/x.webp"})
    assert res.status_code == 401


def test_delete_skips_url_not_from_our_storage(admin_client):
    res = admin_client.delete("/api/images", json={"url": "https://admin-pasted-external.example.com/pic.jpg"})
    assert res.status_code == 200
    assert res.get_json()["reason"] == "not_ours"


# ---------------------------------------------------------------------
# Regression: the upload pipeline returns both a main image URL and a
# thumbnail URL, but only `image` was ever persisted on the product — the
# thumbnail was silently orphaned in storage forever, with no way to find
# or clean it up on replace/delete. `thumbnail` must round-trip through
# product create/update the same way `image` does.
# ---------------------------------------------------------------------
def test_product_create_and_update_persist_thumbnail_field(db):
    from backend.services.products_service import create_product, update_product, delete_product

    pid_sku = "QA-THUMB-TEST-1"
    db.products.delete_many({"sku": pid_sku})
    created = create_product({
        "sku": pid_sku, "cat": "gifts", "catLabel": "מתנות", "name": "מוצר עם תמונה ממוזערת",
        "price": 10, "stock": 1, "threshold": 1,
        "image": "https://cdn.example.com/products/abc.webp",
        "thumbnail": "https://cdn.example.com/products/thumbs/abc.webp",
    })
    try:
        assert created["thumbnail"] == "https://cdn.example.com/products/thumbs/abc.webp"
        stored = db.products.find_one({"_id": created["id"]})
        assert stored["thumbnail"] == "https://cdn.example.com/products/thumbs/abc.webp"

        updated = update_product(created["id"], {"thumbnail": "https://cdn.example.com/products/thumbs/def.webp"})
        assert updated["thumbnail"] == "https://cdn.example.com/products/thumbs/def.webp"
    finally:
        delete_product(created["id"])


TEST_BLOB_URL_PREFIX = "https://testStoreId123.public.blob.vercel-storage.com"


def test_delete_product_image_succeeds_when_not_referenced_anywhere(db, monkeypatch):
    from backend.services import images_service
    from backend.images import storage

    delete_calls = []
    monkeypatch.setattr(storage, "delete_object", lambda url: delete_calls.append(url))

    url = f"{TEST_BLOB_URL_PREFIX}/products/orphaned-{uuid4().hex}.webp"
    db.products.delete_many({"image": url})  # guard against a stale leftover from a prior failed run

    result = images_service.delete_product_image(url)
    assert result == {"deleted": True}
    assert delete_calls == [url]


def test_delete_product_image_checks_thumbnail_field_too(db, monkeypatch):
    from backend.services import images_service
    from backend.images import storage

    monkeypatch.setattr(storage, "delete_object", lambda url: None)

    pid_sku = "QA-THUMB-TEST-2"
    db.products.delete_many({"sku": pid_sku})
    from backend.services.products_service import create_product, delete_product
    created = create_product({
        "sku": pid_sku, "cat": "gifts", "catLabel": "מתנות", "name": "מוצר",
        "price": 10, "stock": 1, "threshold": 1,
        "thumbnail": f"{TEST_BLOB_URL_PREFIX}/products/thumbs/still-used.webp",
    })
    try:
        result = images_service.delete_product_image(f"{TEST_BLOB_URL_PREFIX}/products/thumbs/still-used.webp")
        assert result == {"deleted": False, "reason": "in_use"}
    finally:
        delete_product(created["id"])


# ---------------------------------------------------------------------
# Vercel Blob storage layer (backend/images/storage.py) — pure key/URL
# logic needs no network; upload/delete are tested against a mocked
# `requests` layer so these run without real Blob credentials.
# ---------------------------------------------------------------------

def test_key_from_url_recognizes_our_public_blob_host():
    from backend.images import storage
    url = f"{TEST_BLOB_URL_PREFIX}/products/abc123.webp"
    assert storage.key_from_url(url) == "products/abc123.webp"


def test_key_from_url_rejects_external_or_legacy_urls():
    from backend.images import storage
    assert storage.key_from_url("https://admin-pasted-external.example.com/pic.jpg") is None
    assert storage.key_from_url("https://evil.com/products/abc123.webp") is None
    assert storage.key_from_url(None) is None
    assert storage.key_from_url("") is None
    assert storage.key_from_url("javascript:alert(1)") is None


def test_key_from_url_rejects_plain_http_even_on_the_right_host():
    # Only https is ever a real Blob URL — a plain-http lookalike is not ours.
    from backend.images import storage
    assert storage.key_from_url(f"http://testStoreId123.public.blob.vercel-storage.com/x.webp") is None


# ---------------------------------------------------------------------
# bereshit-images-public is connected under a custom "BERESHIT_IMAGES"
# variable prefix — a second, older store's unprefixed BLOB_* variables
# still exist in the Vercel project (kept around intentionally, not yet
# removed) and must never be read here, or an upload could silently land
# in the wrong/old store.
# ---------------------------------------------------------------------

def test_storage_reads_the_new_prefixed_token_env_var(monkeypatch):
    from backend.images import storage
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("BERESHIT_IMAGES_READ_WRITE_TOKEN", "the-real-new-store-token")
    assert storage._token() == "the-real-new-store-token"
    assert storage.is_configured() is True


def test_storage_never_falls_back_to_the_old_unprefixed_blob_token(monkeypatch):
    from backend.images import storage
    monkeypatch.delenv("BERESHIT_IMAGES_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "old-store-token-must-not-be-used")
    assert storage._token() is None
    assert storage.is_configured() is False


def test_storage_reads_the_new_prefixed_store_id_env_var(monkeypatch):
    from backend.images import storage
    monkeypatch.delenv("BLOB_STORE_ID", raising=False)
    monkeypatch.setenv("BERESHIT_IMAGES_STORE_ID", "newstoreid456")
    assert storage.public_url_for_key("products/x.webp") == "https://newstoreid456.public.blob.vercel-storage.com/products/x.webp"


def test_storage_never_falls_back_to_the_old_unprefixed_store_id(monkeypatch):
    from backend.images import storage
    monkeypatch.delenv("BERESHIT_IMAGES_STORE_ID", raising=False)
    monkeypatch.setenv("BLOB_STORE_ID", "oldstoreid123")
    assert storage.public_url_for_key("products/x.webp") is None


# ---------------------------------------------------------------------
# Regression: production incident — "Vercel Blob delete failed (400):
# Some urls are malformed". Root cause: Vercel provisions
# BERESHIT_IMAGES_STORE_ID WITH a "store_" prefix (confirmed by reading
# @vercel/blob's own compiled source, which strips this exact prefix
# before building any hostname), but this module built the public CDN
# URL directly from the raw env var — producing a hostname with an
# underscore in it (invalid per RFC 1035), which Vercel Blob's delete API
# correctly rejected as malformed.
# ---------------------------------------------------------------------

def test_store_id_strips_the_store_prefix_vercel_actually_provisions(monkeypatch):
    from backend.images import storage
    monkeypatch.setenv("BERESHIT_IMAGES_STORE_ID", "store_abc123xyz")
    assert storage._store_id() == "abc123xyz"
    assert storage.public_url_for_key("staging/x.upload") == "https://abc123xyz.public.blob.vercel-storage.com/staging/x.upload"


def test_store_id_left_unchanged_when_it_has_no_store_prefix(monkeypatch):
    from backend.images import storage
    monkeypatch.setenv("BERESHIT_IMAGES_STORE_ID", "abc123xyz")
    assert storage._store_id() == "abc123xyz"


def test_key_from_url_rejects_a_hostname_containing_an_underscore():
    """The exact shape of the bug: a URL that ends with the right suffix
    but whose host has a "store_..." prefix baked in is not a real,
    resolvable hostname (underscores aren't legal in a DNS label) and
    must never be treated as one of ours, regardless of the suffix
    match — this is what stops a malformed URL from ever reaching
    Vercel Blob's delete API in the first place."""
    from backend.images import storage
    bad = "https://store_abc123xyz.public.blob.vercel-storage.com/products/x.webp"
    assert storage.key_from_url(bad) is None


def test_key_from_url_still_accepts_a_normal_well_formed_url():
    from backend.images import storage
    good = f"{TEST_BLOB_URL_PREFIX}/products/x.webp"
    assert storage.key_from_url(good) == "products/x.webp"


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def test_upload_bytes_puts_to_blob_api_and_returns_url(monkeypatch):
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "vercel_blob_rw_teststoreid456_secretpart")

    captured = {}

    def fake_put(url, params=None, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["data"] = data
        return _FakeResponse(200, {"url": f"{TEST_BLOB_URL_PREFIX}/{params['pathname']}"})

    monkeypatch.setattr(storage.requests, "put", fake_put)

    result_url = storage.upload_bytes(b"fake-webp-bytes", "products/xyz.webp", "image/webp")

    assert result_url == f"{TEST_BLOB_URL_PREFIX}/products/xyz.webp"
    assert captured["headers"]["authorization"] == "Bearer vercel_blob_rw_teststoreid456_secretpart"
    # Regression: an earlier, outdated header name ("access" instead of
    # "x-vercel-blob-access") and API version ("7" instead of "12") were
    # silently accepted as a well-formed request shape locally (nothing
    # here calls the real API), but the real, current Blob API rejected
    # it in production with "Invalid pathname" — verified against
    # @vercel/blob@2.8.0's actual compiled source, not guessed.
    assert captured["headers"]["x-vercel-blob-access"] == "public"
    assert "access" not in captured["headers"]
    assert captured["headers"]["x-api-version"] == "12"
    assert captured["headers"]["x-vercel-blob-store-id"] == "teststoreid456"
    assert captured["headers"]["x-content-type"] == "image/webp"
    # Never leak the token in the URL/params — only in the auth header.
    assert "secretpart" not in str(captured["params"])


def test_store_id_from_token_extracts_the_fourth_underscore_segment():
    from backend.images import storage
    assert storage._store_id_from_token("vercel_blob_rw_abc123_therest_of_the_secret") == "abc123"
    assert storage._store_id_from_token("") == ""
    assert storage._store_id_from_token("not-enough-underscore-segments") == ""


def test_upload_bytes_raises_runtime_error_on_non_200(monkeypatch):
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "fake-rw-token")
    monkeypatch.setattr(
        storage.requests, "put",
        lambda *a, **k: _FakeResponse(403, text="forbidden — store is private"),
    )
    with pytest.raises(RuntimeError):
        storage.upload_bytes(b"data", "products/xyz.webp", "image/webp")


def test_delete_object_calls_blob_delete_endpoint_for_our_own_url(monkeypatch):
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "vercel_blob_rw_teststoreid456_secretpart")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(200, {})

    monkeypatch.setattr(storage.requests, "post", fake_post)

    storage.delete_object(f"{TEST_BLOB_URL_PREFIX}/products/xyz.webp")

    assert captured["url"] == f"{storage._BLOB_API_BASE}/delete"
    assert captured["json"] == {"urls": [f"{TEST_BLOB_URL_PREFIX}/products/xyz.webp"]}
    assert captured["headers"]["x-api-version"] == "12"
    assert captured["headers"]["x-vercel-blob-store-id"] == "teststoreid456"


def test_delete_object_never_calls_blob_api_for_external_url(monkeypatch):
    """Deleting an admin-pasted/imported external URL, or one from another
    host entirely, must never reach the Blob API at all — regardless of
    whether it happens to be `is_configured()`."""
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "fake-rw-token")

    called = {"count": 0}

    def fake_post(*a, **k):
        called["count"] += 1
        return _FakeResponse(200, {})

    monkeypatch.setattr(storage.requests, "post", fake_post)

    storage.delete_object("https://admin-pasted-external.example.com/pic.jpg")
    assert called["count"] == 0


def test_upload_product_image_rolls_back_main_when_thumbnail_upload_fails(monkeypatch):
    from backend.services import images_service
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "fake-rw-token")

    put_calls = []
    delete_calls = []

    def fake_put(url, params=None, headers=None, data=None, timeout=None):
        put_calls.append(params["pathname"])
        if len(put_calls) == 1:
            return _FakeResponse(200, {"url": f"{TEST_BLOB_URL_PREFIX}/{params['pathname']}"})
        return _FakeResponse(500, text="thumbnail upload failed")

    def fake_post(url, headers=None, json=None, timeout=None):
        delete_calls.append(json["urls"])
        return _FakeResponse(200, {})

    monkeypatch.setattr(storage.requests, "put", fake_put)
    monkeypatch.setattr(storage.requests, "post", fake_post)

    with pytest.raises(RuntimeError):
        images_service.upload_product_image(make_image_bytes(300, 300, "PNG"))

    # The main image upload succeeded before the thumbnail failed — it
    # must be cleaned up rather than left orphaned in the Blob store.
    assert len(put_calls) == 2
    assert len(delete_calls) == 1
    assert delete_calls[0] == [f"{TEST_BLOB_URL_PREFIX}/{put_calls[0]}"]


def test_upload_product_image_returns_main_and_thumbnail_urls_on_success(monkeypatch):
    from backend.services import images_service
    from backend.images import storage
    monkeypatch.setattr(storage, "_token", lambda: "fake-rw-token")

    def fake_put(url, params=None, headers=None, data=None, timeout=None):
        return _FakeResponse(200, {"url": f"{TEST_BLOB_URL_PREFIX}/{params['pathname']}"})

    monkeypatch.setattr(storage.requests, "put", fake_put)

    result = images_service.upload_product_image(make_image_bytes(500, 500, "PNG"))
    assert result["url"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/")
    assert result["thumbnailUrl"].startswith(f"{TEST_BLOB_URL_PREFIX}/products/thumbs/")
    assert result["url"] != result["thumbnailUrl"]
    assert result["width"] == 500 and result["height"] == 500


# ---------------------------------------------------------------------
# Authorization matrix on the image routes
# ---------------------------------------------------------------------

def test_upload_forbidden_for_role_without_products_write(db):
    from backend.auth.security import hash_password
    from backend.auth.roles import ORDERS_MANAGER

    admin_id = "AU-TEST-IMG-ORDMGR"
    email = "test-img-ordmgr@bereshit.test"
    db.admin_users.delete_one({"_id": admin_id})
    db.admin_users.insert_one({
        "_id": admin_id, "name": "Ord Mgr", "email": email,
        "passwordHash": hash_password("TestOrdMgr123!"), "role": ORDERS_MANAGER, "active": True,
    })
    try:
        c = flask_app.test_client()
        login = c.post("/api/auth/admin/login", json={"email": email, "password": "TestOrdMgr123!"})
        assert login.status_code == 200, login.get_json()

        auth_res = c.get("/api/images/upload-authorize")
        assert auth_res.status_code == 403

        process_res = c.post("/api/images/process", json={"pathname": "staging/" + "b" * 32 + ".upload"})
        assert process_res.status_code == 403

        del_res = c.delete("/api/images", json={"url": f"{TEST_BLOB_URL_PREFIX}/products/x.webp"})
        assert del_res.status_code == 403
    finally:
        db.admin_users.delete_one({"_id": admin_id})


# ---------------------------------------------------------------------
# Product image URL fields reject non-http(s) schemes at the model layer
# (defense in depth alongside the frontend's own URL/scheme validation).
# ---------------------------------------------------------------------

def test_product_create_rejects_javascript_scheme_image_url(db):
    from backend.services.products_service import create_product
    from backend.models.schemas import ValidationError as SchemaValidationError

    pid_sku = "QA-XSS-IMG-TEST-1"
    db.products.delete_many({"sku": pid_sku})
    with pytest.raises(SchemaValidationError):
        create_product({
            "sku": pid_sku, "cat": "gifts", "catLabel": "מתנות", "name": "מוצר",
            "price": 10, "stock": 1, "threshold": 1,
            "image": "javascript:alert(1)",
        })
    assert db.products.find_one({"sku": pid_sku}) is None


def test_product_update_rejects_data_scheme_thumbnail_url(db):
    from backend.services.products_service import create_product, update_product, delete_product
    from backend.models.schemas import ValidationError as SchemaValidationError

    pid_sku = "QA-XSS-IMG-TEST-2"
    db.products.delete_many({"sku": pid_sku})
    created = create_product({
        "sku": pid_sku, "cat": "gifts", "catLabel": "מתנות", "name": "מוצר",
        "price": 10, "stock": 1, "threshold": 1,
    })
    try:
        with pytest.raises(SchemaValidationError):
            update_product(created["id"], {"thumbnail": "data:text/html,<script>alert(1)</script>"})
    finally:
        delete_product(created["id"])
