from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from models.schemas import ValidationError
from services import products_service as svc

bp = Blueprint("products", __name__, url_prefix="/api/products")


@bp.get("")
def list_products():
    try:
        filters = {"cat": request.args.get("cat"), "status": request.args.get("status")}
        return jsonify(svc.list_products(filters)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing products"}), 500


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
def update_product(product_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        product = svc.update_product(product_id, data)
        if not product:
            return jsonify({"error": f"Product {product_id} not found"}), 404
        return jsonify(product), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating product"}), 500


@bp.delete("/<int:product_id>")
def delete_product(product_id):
    try:
        deleted = svc.delete_product(product_id)
        if not deleted:
            return jsonify({"error": f"Product {product_id} not found"}), 404
        return jsonify({"message": f"Product {product_id} deleted"}), 200
    except PyMongoError:
        return jsonify({"error": "Database error while deleting product"}), 500
