from flask import Blueprint, jsonify
from pymongo.errors import PyMongoError

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
