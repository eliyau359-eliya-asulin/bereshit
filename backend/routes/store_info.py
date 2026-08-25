from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from models.schemas import ValidationError
from services import store_info_service as svc

bp = Blueprint("store_info", __name__, url_prefix="/api/store-info")


@bp.get("")
def get_store_info():
    try:
        info = svc.get_store_info()
        if not info:
            return jsonify({"error": "Store info has not been seeded yet"}), 404
        return jsonify(info), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching store info"}), 500


@bp.put("")
def update_store_info():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        info = svc.update_store_info(data)
        return jsonify(info), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating store info"}), 500
