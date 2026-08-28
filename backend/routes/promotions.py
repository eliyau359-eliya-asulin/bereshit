from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import promotions_service as svc
from backend.auth.decorators import require_admin

bp = Blueprint("promotions", __name__, url_prefix="/api/promotions")


@bp.get("")
def list_promotions():
    try:
        return jsonify(svc.list_promotions()), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing promotions"}), 500


@bp.get("/<promo_id>")
def get_promotion(promo_id):
    try:
        promo = svc.get_promotion(promo_id)
        if not promo:
            return jsonify({"error": f"Promotion '{promo_id}' not found"}), 404
        return jsonify(promo), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching promotion"}), 500


@bp.post("")
@require_admin("promotions:write")
def create_promotion():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        promo = svc.create_promotion(data)
        return jsonify(promo), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while creating promotion"}), 500


@bp.put("/<promo_id>")
@require_admin("promotions:write")
def update_promotion(promo_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        promo = svc.update_promotion(promo_id, data)
        if not promo:
            return jsonify({"error": f"Promotion '{promo_id}' not found"}), 404
        return jsonify(promo), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating promotion"}), 500
