from flask import Blueprint, request, jsonify, g, Response
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import products_service as svc
from backend.services import import_service
from backend.auth.decorators import require_admin

bp = Blueprint("products", __name__, url_prefix="/api/products")

# A PUT to this route serves two different privilege levels through one
# endpoint: a plain stock/reason adjustment (inventory screen, barcode
# scanner) only needs 'products:stock', while touching any other field
# (name, price, description, ...) needs the full 'products:write'
# permission. Both roles may call the route at all; which fields are
# actually present in the patch decides which permission is required.
_STOCK_ONLY_FIELDS = {"stock", "reason", "status"}


@bp.get("")
def list_products():
    try:
        filters = {"cat": request.args.get("cat"), "status": request.args.get("status")}
        return jsonify(svc.list_products(filters)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing products"}), 500


@bp.get("/inventory-log")
@require_admin("products:write", "products:stock")
def get_inventory_log():
    try:
        product_id = request.args.get("productId", type=int)
        page = request.args.get("page", default=1, type=int) or 1
        page_size = request.args.get("pageSize", default=50, type=int) or 50
        return jsonify(svc.list_inventory_log(product_id, page, page_size)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing inventory log"}), 500


@bp.get("/lookup")
@require_admin("products:write", "products:stock")
def lookup_product():
    code = request.args.get("code")
    try:
        product = svc.find_by_code(code)
        if not product:
            return jsonify({"error": f"לא נמצא מוצר עם ברקוד/מק\"ט '{code}'"}), 404
        return jsonify(product), 200
    except PyMongoError:
        return jsonify({"error": "Database error while looking up product"}), 500


@bp.get("/<int:product_id>")
def get_product(product_id):
    try:
        product = svc.get_product(product_id)
        if not product:
            return jsonify({"error": f"Product {product_id} not found"}), 404
        return jsonify(product), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching product"}), 500


@bp.post("")
@require_admin("products:write")
def create_product():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        product = svc.create_product(data)
        return jsonify(product), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while creating product"}), 500


@bp.put("/<int:product_id>")
@require_admin("products:write", "products:stock")
def update_product(product_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    touches_non_stock_fields = any(k not in _STOCK_ONLY_FIELDS for k in data.keys())
    if touches_non_stock_fields:
        from backend.auth.roles import has_permission
        if not has_permission(g.admin.get("role"), ["products:write"]):
            return jsonify({"error": "אין הרשאה לערוך שדות מוצר מלאים — רק מלאי", "code": "FORBIDDEN"}), 403

    try:
        actor = {"id": g.admin["userId"], "name": g.admin.get("name")}
        product = svc.update_product(product_id, data, actor=actor)
        if not product:
            return jsonify({"error": f"Product {product_id} not found"}), 404
        return jsonify(product), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating product"}), 500


@bp.delete("/<int:product_id>")
@require_admin("products:write")
def delete_product(product_id):
    try:
        deleted = svc.delete_product(product_id)
        if not deleted:
            return jsonify({"error": f"Product {product_id} not found"}), 404
        return jsonify({"message": f"Product {product_id} deleted"}), 200
    except PyMongoError:
        return jsonify({"error": "Database error while deleting product"}), 500


# ============================= Bulk import ==============================

@bp.get("/import/template")
@require_admin("products:write")
def import_template():
    csv_bytes = import_service.build_template_csv()
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=bereshit-products-template.csv"},
    )


@bp.post("/import/preview")
@require_admin("products:write")
def import_preview():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "לא נשלח קובץ תחת השדה 'file'"}), 400
    try:
        raw_rows = import_service.parse_import_file(file.read(), file.filename)
        report = import_service.validate_rows(raw_rows)
        return jsonify(report), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while validating the import"}), 500


@bp.post("/import/apply")
@require_admin("products:write")
def import_apply():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("rows"), list):
        return jsonify({"error": "Request body must include a 'rows' array (from /import/preview)"}), 400
    try:
        actor = {"id": g.admin["userId"], "name": g.admin.get("name")}
        result = import_service.apply_import(data["rows"], actor=actor)
        return jsonify(result), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while applying the import"}), 500
