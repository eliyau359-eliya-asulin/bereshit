from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import orders_service as svc

bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@bp.get("")
def list_orders():
    try:
        filters = {"status": request.args.get("status"), "customerId": request.args.get("customerId")}
        return jsonify(svc.list_orders(filters)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing orders"}), 500


@bp.post("")
def create_order():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        order = svc.create_order(data)
        return jsonify({"order": order}), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "שגיאת שרת בעת יצירת ההזמנה. נסו שוב."}), 500


@bp.get("/<order_id>")
def get_order(order_id):
    try:
        order = svc.get_order(order_id)
        if not order:
            return jsonify({"error": f"Order '{order_id}' not found"}), 404
        return jsonify(order), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching order"}), 500


@bp.put("/<order_id>")
def update_order(order_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        order = svc.update_order(order_id, data)
        if not order:
            return jsonify({"error": f"Order '{order_id}' not found"}), 404
        return jsonify(order), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating order"}), 500
