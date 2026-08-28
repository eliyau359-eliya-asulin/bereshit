from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import orders_service as svc
from backend.auth.decorators import require_admin, get_current_admin, get_current_customer

bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@bp.get("")
def list_orders():
    admin = get_current_admin()
    customer = get_current_customer()
    if admin:
        filters = {"status": request.args.get("status"), "customerId": request.args.get("customerId")}
    elif customer:
        # A customer can only ever list THEIR OWN orders — any customerId
        # in the query string is ignored, never trusted.
        filters = {"status": request.args.get("status"), "customerId": customer["userId"]}
    else:
        return jsonify({"error": "נדרשת התחברות", "code": "UNAUTHENTICATED"}), 401
    page = request.args.get("page", type=int)
    page_size = request.args.get("pageSize", type=int)
    try:
        return jsonify(svc.list_orders(filters, page, page_size)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing orders"}), 500


@bp.post("")
def create_order():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    customer = get_current_customer()  # None = guest checkout, still allowed
    try:
        order = svc.create_order(data, session_customer_id=customer["userId"] if customer else None)
        return jsonify({"order": order}), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "שגיאת שרת בעת יצירת ההזמנה. נסו שוב."}), 500


@bp.get("/<order_id>")
def get_order(order_id):
    admin = get_current_admin()
    customer = get_current_customer()
    if not admin and not customer:
        return jsonify({"error": "נדרשת התחברות", "code": "UNAUTHENTICATED"}), 401
    try:
        order = svc.get_order(order_id)
        if not order:
            return jsonify({"error": f"Order '{order_id}' not found"}), 404
        if customer and not admin and order.get("customerId") != customer["userId"]:
            # Same 404 as "doesn't exist" — a customer probing other order
            # ids should not be able to tell the difference.
            return jsonify({"error": f"Order '{order_id}' not found"}), 404
        return jsonify(order), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching order"}), 500


@bp.put("/<order_id>")
@require_admin("orders:write")
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
