from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import categories_service as svc

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("")
def list_categories():
    try:
        return jsonify(svc.list_categories()), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing categories"}), 500


@bp.get("/<key>")
def get_category(key):
    try:
        category = svc.get_category(key)
        if not category:
            return jsonify({"error": f"Category '{key}' not found"}), 404
        return jsonify(category), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching category"}), 500


@bp.post("")
def create_category():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        category = svc.create_category(data)
        return jsonify(category), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while creating category"}), 500


@bp.put("/<key>")
def update_category(key):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        category = svc.update_category(key, data)
        if not category:
            return jsonify({"error": f"Category '{key}' not found"}), 404
        return jsonify(category), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating category"}), 500


@bp.delete("/<key>")
def delete_category(key):
    try:
        result = svc.delete_category(key)
        if not result["deleted"]:
            if result["reason"] == "not_found":
                return jsonify({"error": f"Category '{key}' not found"}), 404
            if result["reason"] == "in_use":
                count = result["productCount"]
                return jsonify({
                    "error": f"לא ניתן למחוק — {count} מוצרים משויכים לקטגוריה זו. "
                             f"יש לשייך אותם לקטגוריה אחרת או למחוק אותם קודם.",
                    "productCount": count,
                }), 409
        return jsonify({"message": f"Category '{key}' deleted"}), 200
    except PyMongoError:
        return jsonify({"error": "Database error while deleting category"}), 500
