"""Phase H: image validation/processing, and the upload/delete routes'
auth + business-rule behavior. There is no real S3-compatible bucket
configured in this test environment (no credentials are available here),
so upload naturally exercises the "storage not configured" path — which
is itself a real, important behavior to verify (a clear 503, never a
silent fake success). The pure validation/resize logic in
backend/images/processing.py is fully testable without any bucket at all
and is covered thoroughly here.
"""
import io
import sys
from pathlib import Path

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
# Route auth + behavior (no real bucket configured in this test env)
# ---------------------------------------------------------------------

def test_upload_requires_admin_auth(client):
    data = {"file": (io.BytesIO(make_image_bytes(300, 300)), "test.png")}
    res = client.post("/api/images/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 401


def test_upload_without_storage_configured_returns_503_not_a_fake_success(admin_client):
    data = {"file": (io.BytesIO(make_image_bytes(300, 300)), "test.png")}
    res = admin_client.post("/api/images/upload", data=data, content_type="multipart/form-data")
    # This test environment has no S3_* credentials configured — the
    # route must say so clearly, never pretend the upload worked.
    assert res.status_code == 503
    assert res.get_json()["code"] == "STORAGE_NOT_CONFIGURED"


def test_upload_rejects_invalid_image_before_ever_touching_storage(admin_client):
    data = {"file": (io.BytesIO(b"not a real image"), "test.png")}
    res = admin_client.post("/api/images/upload", data=data, content_type="multipart/form-data")
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


def test_delete_product_image_checks_thumbnail_field_too(db, monkeypatch):
    from backend.services import images_service
    from backend.images import storage

    # Simulate a configured bucket so key_from_url can resolve the URL,
    # without needing real S3 credentials in this environment.
    monkeypatch.setattr(storage, "_config", lambda: {
        "bucket": "test-bucket", "access_key": "x", "secret_key": "x", "region": "us-east-1",
        "endpoint_url": None, "public_base_url": "https://cdn.example.com", "use_public_acl": False,
    })
    monkeypatch.setattr(storage, "delete_object", lambda key: None)

    pid_sku = "QA-THUMB-TEST-2"
    db.products.delete_many({"sku": pid_sku})
    from backend.services.products_service import create_product, delete_product
    created = create_product({
        "sku": pid_sku, "cat": "gifts", "catLabel": "מתנות", "name": "מוצר",
        "price": 10, "stock": 1, "threshold": 1,
        "thumbnail": "https://cdn.example.com/products/thumbs/still-used.webp",
    })
    try:
        result = images_service.delete_product_image("https://cdn.example.com/products/thumbs/still-used.webp")
        assert result == {"deleted": False, "reason": "in_use"}
    finally:
        delete_product(created["id"])
