from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from backend.services import customers_service as svc
from backend.auth.decorators import require_admin

bp = Blueprint("customers", __name__, url_prefix="/api/customers")

# Customer-facing self-service (view/edit "my profile") lives at
# /api/auth/customer/me, not here — every route in this blueprint returns
# another person's private data by design (name/email/phone/order stats),
# so it is admin-only, never reachable with a customer session.


@bp.get("")
@require_admin("customers:read")
def list_customers():
    page = request.args.get("page", type=int)
    page_size = request.args.get("pageSize", type=int)
    try:
        return jsonify(svc.list_customers(page, page_size)), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing customers"}), 500


@bp.get("/<customer_id>")
@require_admin("customers:read")
def get_customer(customer_id):
    try:
        customer = svc.get_customer(customer_id)
        if not customer:
            return jsonify({"error": f"Customer '{customer_id}' not found"}), 404
        return jsonify(customer), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching customer"}), 500
