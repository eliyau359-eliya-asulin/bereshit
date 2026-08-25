from flask import Blueprint, jsonify
from pymongo.errors import PyMongoError

from backend.services import customers_service as svc

bp = Blueprint("customers", __name__, url_prefix="/api/customers")


@bp.get("")
def list_customers():
    try:
        return jsonify(svc.list_customers()), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing customers"}), 500


@bp.get("/<customer_id>")
def get_customer(customer_id):
    try:
        customer = svc.get_customer(customer_id)
        if not customer:
            return jsonify({"error": f"Customer '{customer_id}' not found"}), 404
        return jsonify(customer), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching customer"}), 500
