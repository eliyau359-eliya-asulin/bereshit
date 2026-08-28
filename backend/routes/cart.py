from flask import Blueprint, request, jsonify, g
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import cart_service as svc
from backend.auth.decorators import require_customer

bp = Blueprint("cart", __name__, url_prefix="/api/cart")

# Guest carts never reach the backend at all (they live in the browser's
# localStorage) — every route here is for a logged-in customer's own cart
# only, identified strictly from the session, never from a client-supplied
# customerId, so one customer can never read or overwrite another's cart.


@bp.get("")
@require_customer
def get_cart():
    try:
        return jsonify({"items": svc.get_cart(g.customer["userId"])}), 200
    except PyMongoError:
        return jsonify({"error": "Database error while fetching cart"}), 500


@bp.put("")
@require_customer
def put_cart():
    data = request.get_json(silent=True)
    if data is None or not isinstance(data.get("items"), list):
        return jsonify({"error": "Request body must include an 'items' array"}), 400
    try:
        items = svc.save_cart(g.customer["userId"], data["items"])
        return jsonify({"items": items}), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while saving cart"}), 500
