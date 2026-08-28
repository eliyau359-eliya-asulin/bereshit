from flask import Blueprint, request, jsonify, make_response
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError, ADMIN_LOGIN_SPEC, CUSTOMER_LOGIN_SPEC, validate_fields
from backend.services import customers_service, admin_users_service
from backend.auth.session_store import create_session, delete_session, TYPE_ADMIN, TYPE_CUSTOMER
from backend.auth.cookies import (
    set_session_cookie, clear_session_cookie, ADMIN_COOKIE, CUSTOMER_COOKIE,
)
from backend.auth.decorators import require_admin, require_customer, get_current_admin, get_current_customer
from backend.auth.roles import ROLE_LABELS
from backend.auth.rate_limit import client_ip, is_locked_out, register_failed_attempt, clear_attempts

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ============================== Admin ==============================

@bp.post("/admin/login")
def admin_login():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        validate_fields(data, ADMIN_LOGIN_SPEC, partial=False)
        ip = client_ip()
        email = (data.get("email") or "").strip().lower()
        if is_locked_out("admin", ip, email):
            return jsonify({
                "error": "יותר מדי ניסיונות התחברות כושלים. נסו שוב בעוד כמה דקות.",
                "code": "TOO_MANY_ATTEMPTS",
            }), 429
        admin = admin_users_service.authenticate_admin(data.get("email"), data.get("password"))
        if not admin:
            register_failed_attempt("admin", ip, email)
            return jsonify({"error": "אימייל או סיסמה שגויים", "code": "INVALID_CREDENTIALS"}), 401
        clear_attempts("admin", ip, email)
        token, expires_at = create_session(TYPE_ADMIN, admin["_id"], role=admin["role"], name=admin["name"])
        resp = make_response(jsonify({
            "admin": {
                "id": admin["_id"], "name": admin["name"], "email": admin["email"],
                "role": admin["role"], "roleLabel": ROLE_LABELS.get(admin["role"], admin["role"]),
            }
        }), 200)
        return set_session_cookie(resp, ADMIN_COOKIE, token, expires_at)
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "שגיאת שרת בעת ההתחברות"}), 500


@bp.post("/admin/logout")
def admin_logout():
    token = request.cookies.get(ADMIN_COOKIE)
    delete_session(token)
    resp = make_response(jsonify({"message": "התנתקת בהצלחה"}), 200)
    return clear_session_cookie(resp, ADMIN_COOKIE)


@bp.get("/admin/me")
def admin_me():
    admin_session = get_current_admin()
    if not admin_session:
        return jsonify({"error": "לא מחובר", "code": "UNAUTHENTICATED"}), 401
    try:
        admin = admin_users_service.get_admin_user(admin_session["userId"])
        if not admin or not admin.get("active", True):
            return jsonify({"error": "לא מחובר", "code": "UNAUTHENTICATED"}), 401
        admin["roleLabel"] = ROLE_LABELS.get(admin["role"], admin["role"])
        return jsonify({"admin": admin}), 200
    except PyMongoError:
        return jsonify({"error": "Database error"}), 500


# ============================ Customer ==============================

@bp.post("/customer/register")
def customer_register():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        customer = customers_service.register_customer(data)
        token, expires_at = create_session(TYPE_CUSTOMER, customer["id"])
        resp = make_response(jsonify({"customer": customer}), 201)
        return set_session_cookie(resp, CUSTOMER_COOKIE, token, expires_at)
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "שגיאת שרת בעת ההרשמה"}), 500


@bp.post("/customer/login")
def customer_login():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        validate_fields(data, CUSTOMER_LOGIN_SPEC, partial=False)
        ip = client_ip()
        email = (data.get("email") or "").strip().lower()
        if is_locked_out("customer", ip, email):
            return jsonify({
                "error": "יותר מדי ניסיונות התחברות כושלים. נסו שוב בעוד כמה דקות.",
                "code": "TOO_MANY_ATTEMPTS",
            }), 429
        customer = customers_service.authenticate_customer(data.get("email"), data.get("password"))
        if not customer:
            register_failed_attempt("customer", ip, email)
            return jsonify({"error": "אימייל או סיסמה שגויים", "code": "INVALID_CREDENTIALS"}), 401
        clear_attempts("customer", ip, email)
        token, expires_at = create_session(TYPE_CUSTOMER, customer["_id"])
        resp = make_response(jsonify({
            "customer": {
                "id": customer["_id"], "name": customer["name"],
                "email": customer["email"], "phone": customer.get("phone"),
            }
        }), 200)
        return set_session_cookie(resp, CUSTOMER_COOKIE, token, expires_at)
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "שגיאת שרת בעת ההתחברות"}), 500


@bp.post("/customer/logout")
def customer_logout():
    token = request.cookies.get(CUSTOMER_COOKIE)
    delete_session(token)
    resp = make_response(jsonify({"message": "התנתקת בהצלחה"}), 200)
    return clear_session_cookie(resp, CUSTOMER_COOKIE)


@bp.get("/customer/me")
def customer_me():
    customer_session = get_current_customer()
    if not customer_session:
        return jsonify({"error": "לא מחובר", "code": "UNAUTHENTICATED"}), 401
    try:
        customer = customers_service.get_customer(customer_session["userId"])
        if not customer:
            return jsonify({"error": "לא מחובר", "code": "UNAUTHENTICATED"}), 401
        return jsonify({"customer": customer}), 200
    except PyMongoError:
        return jsonify({"error": "Database error"}), 500


@bp.put("/customer/me")
@require_customer
def customer_update_me():
    from flask import g
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        customer = customers_service.update_customer_profile(g.customer["userId"], data)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        return jsonify({"customer": customer}), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error"}), 500
