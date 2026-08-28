"""Phase I: Excel/CSV bulk product import — validation-before-write,
category/SKU checks, create-vs-update detection, and the transactional
apply step (a bad row never corrupts the catalog).
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import app as flask_app
from backend.db.mongo import get_db
from backend.services import import_service
from backend.models.schemas import ValidationError

TEST_PRODUCT_ID_START = 940001
TEST_CATEGORY_KEY = "qa-import-cat"


@pytest.fixture()
def client():
    flask_app.testing = True
    return flask_app.test_client()


@pytest.fixture()
def db():
    return get_db()


@pytest.fixture()
def category(db):
    db.categories.delete_one({"_id": TEST_CATEGORY_KEY})
    db.categories.insert_one({"_id": TEST_CATEGORY_KEY, "label": "קטגוריית בדיקה", "status": "active", "order": 999})
    yield "קטגוריית בדיקה"
    db.categories.delete_one({"_id": TEST_CATEGORY_KEY})


def csv_bytes(rows):
    header = ",".join(import_service.COLUMNS)
    lines = [header]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in import_service.COLUMNS))
    return ("﻿" + "\r\n".join(lines)).encode("utf-8")


def make_row(sku, name="מוצר בדיקה", category="קטגוריית בדיקה", price="100", stock="10", **overrides):
    row = {"SKU": sku, "Name": name, "Category": category, "Price": price, "Stock": stock, "Threshold": "5"}
    row.update(overrides)
    return row


# ---------------------------------------------------------------------
# Parsing + validation (pure logic, no writes)
# ---------------------------------------------------------------------

def test_valid_csv_rows_parsed_and_validated(db, category):
    sku = f"IMPORT-{TEST_PRODUCT_ID_START}-1"
    data = csv_bytes([make_row(sku)])
    rows = import_service.parse_import_file(data, "products.csv")
    report = import_service.validate_rows(rows)
    assert report["summary"]["valid"] == 1
    assert report["summary"]["toCreate"] == 1
    assert report["rows"][0]["valid"] is True


def test_missing_required_column_rejected():
    bad_csv = ("﻿SKU,Name\r\nX,Y\r\n").encode("utf-8")
    with pytest.raises(ValidationError):
        import_service.parse_import_file(bad_csv, "products.csv")


def test_unsupported_file_extension_rejected():
    with pytest.raises(ValidationError):
        import_service.parse_import_file(b"whatever", "products.pdf")


def test_row_with_missing_sku_flagged_invalid(category):
    rows = import_service.parse_import_file(csv_bytes([make_row("")]), "products.csv")
    report = import_service.validate_rows(rows)
    assert report["rows"][0]["valid"] is False
    assert any("מק" in e for e in report["rows"][0]["errors"])


def test_row_with_unknown_category_flagged_invalid(db):
    rows = import_service.parse_import_file(
        csv_bytes([make_row("IMPORT-X", category="קטגוריה שלא קיימת")]), "products.csv"
    )
    report = import_service.validate_rows(rows)
    assert report["rows"][0]["valid"] is False
    assert any("קטגוריה" in e for e in report["rows"][0]["errors"])


def test_row_with_invalid_price_flagged_invalid(category):
    rows = import_service.parse_import_file(csv_bytes([make_row("IMPORT-X", price="not-a-number")]), "products.csv")
    report = import_service.validate_rows(rows)
    assert report["rows"][0]["valid"] is False


def test_duplicate_sku_within_file_flagged_invalid(category):
    rows = import_service.parse_import_file(
        csv_bytes([make_row("DUP-SKU"), make_row("DUP-SKU")]), "products.csv"
    )
    report = import_service.validate_rows(rows)
    assert report["rows"][1]["valid"] is False
    assert any("יותר מפעם אחת" in e for e in report["rows"][1]["errors"])


def test_existing_sku_detected_as_update(db, category):
    pid = TEST_PRODUCT_ID_START + 2
    sku = f"IMPORT-EXISTING-{pid}"
    db.products.delete_one({"_id": pid})
    db.products.insert_one({
        "_id": pid, "sku": sku, "cat": TEST_CATEGORY_KEY, "catLabel": category,
        "name": "מוצר קיים", "price": 50, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": 5, "threshold": 2, "status": "active", "sold": 0, "image": None,
    })
    try:
        rows = import_service.parse_import_file(csv_bytes([make_row(sku, stock="8")]), "products.csv")
        report = import_service.validate_rows(rows)
        assert report["rows"][0]["action"] == "update"
        assert report["summary"]["toUpdate"] == 1
    finally:
        db.products.delete_one({"_id": pid})


# ---------------------------------------------------------------------
# apply_import — real writes, transactional
# ---------------------------------------------------------------------

def test_apply_import_creates_new_product_and_logs_nothing_fake(db, category):
    sku = f"IMPORT-APPLY-{TEST_PRODUCT_ID_START}"
    db.products.delete_many({"sku": sku})
    try:
        rows = import_service.parse_import_file(csv_bytes([make_row(sku, stock="7")]), "products.csv")
        report = import_service.validate_rows(rows)
        result = import_service.apply_import(report["rows"], actor={"id": "AU-TEST", "name": "Tester"})
        assert result["created"] == 1
        assert result["updated"] == 0

        created = db.products.find_one({"sku": sku})
        assert created is not None
        assert created["stock"] == 7
        assert created["cat"] == TEST_CATEGORY_KEY
        # Creates don't fabricate inventory history — no prior state to compare against.
        assert db.inventory_log.find_one({"productId": created["_id"]}) is None
    finally:
        db.inventory_log.delete_many({"productName": {"$regex": "מוצר בדיקה"}})
        db.products.delete_many({"sku": sku})


def test_apply_import_updates_existing_product_and_logs_stock_change(db, category):
    pid = TEST_PRODUCT_ID_START + 3
    sku = f"IMPORT-UPDATE-{pid}"
    db.products.delete_one({"_id": pid})
    db.inventory_log.delete_many({"productId": pid})
    db.products.insert_one({
        "_id": pid, "sku": sku, "cat": TEST_CATEGORY_KEY, "catLabel": category,
        "name": "לפני עדכון", "price": 50, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": 3, "threshold": 2, "status": "active", "sold": 0, "image": None,
    })
    try:
        rows = import_service.parse_import_file(
            csv_bytes([make_row(sku, name="אחרי עדכון", stock="20")]), "products.csv"
        )
        report = import_service.validate_rows(rows)
        result = import_service.apply_import(report["rows"], actor={"id": "AU-TEST", "name": "Tester"})
        assert result["updated"] == 1
        assert result["created"] == 0

        updated = db.products.find_one({"_id": pid})
        assert updated["name"] == "אחרי עדכון"
        assert updated["stock"] == 20

        log = db.inventory_log.find_one({"productId": pid})
        assert log is not None
        assert log["previousStock"] == 3
        assert log["newStock"] == 20
        assert log["reason"] == "ייבוא מקובץ Excel/CSV"
        assert log["actor"]["id"] == "AU-TEST"
    finally:
        db.inventory_log.delete_many({"productId": pid})
        db.products.delete_one({"_id": pid})


def test_apply_import_two_blank_barcode_rows_both_create_without_collision(db, category):
    # Regression: products.barcode is a unique+sparse index; a blank Barcode
    # cell must never become an explicit null in the written document, or
    # the second row's insert collides with the first (DuplicateKeyError
    # inside apply_import's transaction, silently failing the whole batch).
    sku_a = f"IMPORT-BLANKBC-A-{TEST_PRODUCT_ID_START}"
    sku_b = f"IMPORT-BLANKBC-B-{TEST_PRODUCT_ID_START}"
    db.products.delete_many({"sku": {"$in": [sku_a, sku_b]}})
    try:
        rows = import_service.parse_import_file(
            csv_bytes([make_row(sku_a), make_row(sku_b)]), "products.csv"
        )
        report = import_service.validate_rows(rows)
        assert report["summary"]["invalid"] == 0, report["rows"]
        result = import_service.apply_import(report["rows"], actor=None)
        assert result["created"] == 2, result
        assert "barcode" not in db.products.find_one({"sku": sku_a})
        assert "barcode" not in db.products.find_one({"sku": sku_b})
    finally:
        db.products.delete_many({"sku": {"$in": [sku_a, sku_b]}})


def test_apply_import_blank_barcode_on_update_does_not_wipe_existing_barcode(db, category):
    pid = TEST_PRODUCT_ID_START + 20
    sku = f"IMPORT-KEEPBC-{pid}"
    db.products.delete_one({"_id": pid})
    db.products.insert_one({
        "_id": pid, "sku": sku, "cat": TEST_CATEGORY_KEY, "catLabel": category, "barcode": "123123123",
        "name": "מוצר עם ברקוד קיים", "price": 50, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": 3, "threshold": 2, "status": "active", "sold": 0, "image": None,
    })
    try:
        # The re-uploaded row's Barcode column is blank — must not clear the
        # barcode the product already has in MongoDB.
        rows = import_service.parse_import_file(csv_bytes([make_row(sku, stock="9")]), "products.csv")
        report = import_service.validate_rows(rows)
        assert report["rows"][0]["action"] == "update"
        result = import_service.apply_import(report["rows"], actor=None)
        assert result["updated"] == 1
        updated = db.products.find_one({"_id": pid})
        assert updated["stock"] == 9
        assert updated["barcode"] == "123123123"
    finally:
        db.products.delete_one({"_id": pid})


def test_duplicate_barcode_within_file_flagged_invalid(category):
    rows = import_service.parse_import_file(csv_bytes([
        make_row("DUPBC-A", Barcode="7770001112"),
        make_row("DUPBC-B", Barcode="7770001112"),
    ]), "products.csv")
    report = import_service.validate_rows(rows)
    assert report["rows"][1]["valid"] is False
    assert any("ברקוד" in e for e in report["rows"][1]["errors"])


def test_barcode_colliding_with_existing_db_product_flagged_invalid(db, category):
    pid = TEST_PRODUCT_ID_START + 21
    db.products.delete_one({"_id": pid})
    db.products.insert_one({
        "_id": pid, "sku": f"EXIST-{pid}", "cat": TEST_CATEGORY_KEY, "catLabel": category, "barcode": "4440005556",
        "name": "מוצר קיים עם ברקוד", "price": 50, "oldPrice": None, "badge": None,
        "short": "", "desc": "", "material": "", "dim": "",
        "stock": 3, "threshold": 2, "status": "active", "sold": 0, "image": None,
    })
    try:
        rows = import_service.parse_import_file(
            csv_bytes([make_row("IMPORT-COLLIDE", Barcode="4440005556")]), "products.csv"
        )
        report = import_service.validate_rows(rows)
        assert report["rows"][0]["valid"] is False
        assert any("ברקוד" in e for e in report["rows"][0]["errors"])
    finally:
        db.products.delete_one({"_id": pid})


def test_cell_strips_trailing_dot_zero_from_whole_number_float():
    # Regression: openpyxl returns a digit-only .xlsx cell (a barcode/SKU
    # typed without formatting the column as text) as a Python float —
    # str()'ing it directly bakes a literal ".0" onto a real barcode/SKU,
    # so the scanner/lookup (exact string match) can never find it again.
    assert import_service._cell({"Barcode": 7290000000001.0}, "Barcode") == "7290000000001"
    assert import_service._cell({"Barcode": 12345}, "Barcode") == "12345"
    assert import_service._cell({"Barcode": "7290000000001"}, "Barcode") == "7290000000001"
    assert import_service._cell({"Price": 19.99}, "Price") == "19.99"  # a genuine decimal must survive


def test_apply_import_only_writes_valid_rows(db, category):
    good_sku = f"IMPORT-MIXED-GOOD-{TEST_PRODUCT_ID_START}"
    db.products.delete_many({"sku": good_sku})
    try:
        rows = import_service.parse_import_file(
            csv_bytes([make_row(good_sku), make_row("", name="שורה פגומה")]), "products.csv"
        )
        report = import_service.validate_rows(rows)
        assert report["summary"]["invalid"] == 1
        result = import_service.apply_import(report["rows"], actor=None)
        assert result["created"] == 1  # only the valid row was written
        assert db.products.find_one({"sku": good_sku}) is not None
    finally:
        db.products.delete_many({"sku": good_sku})


# ---------------------------------------------------------------------
# Routes: auth + template download
# ---------------------------------------------------------------------

def test_import_endpoints_require_admin(client):
    assert client.get("/api/products/import/template").status_code == 401
    assert client.post("/api/products/import/preview", data={}, content_type="multipart/form-data").status_code == 401
    assert client.post("/api/products/import/apply", json={"rows": []}).status_code == 401


def test_template_download_returns_csv_with_expected_columns(admin_client):
    res = admin_client.get("/api/products/import/template")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    text = res.get_data(as_text=True)
    for col in import_service.COLUMNS:
        assert col in text


def test_preview_route_end_to_end(admin_client, db, category):
    sku = f"IMPORT-ROUTE-{TEST_PRODUCT_ID_START}"
    data = {"file": (io.BytesIO(csv_bytes([make_row(sku)])), "products.csv")}
    res = admin_client.post("/api/products/import/preview", data=data, content_type="multipart/form-data")
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["summary"]["valid"] == 1
