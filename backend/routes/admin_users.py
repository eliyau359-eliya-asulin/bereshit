from flask import Blueprint, request, jsonify, g
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import admin_users_service as svc
from backend.auth.decorators import require_admin

bp = Blueprint("admin_users", __name__, url_prefix="/api/admin/users")


@bp.get("")
@require_admin("admin_users:write")
def list_admin_users():
    try:
        return jsonify(svc.list_admin_users()), 200
    except PyMongoError:
        return jsonify({"error": "Database error while listing admin users"}), 500


@bp.post("")
@require_admin("admin_users:write")
def create_admin_user():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        admin = svc.create_admin_user(data)
        return jsonify(admin), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while creating admin user"}), 500


@bp.put("/<admin_id>")
@require_admin("admin_users:write")
def update_admin_user(admin_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    if admin_id == g.admin["userId"] and data.get("active") is False:
        return jsonify({"error": "לא ניתן להשבית את המשתמש המחובר כרגע"}), 400
    try:
        admin = svc.update_admin_user(admin_id, data)
        if not admin:
            return jsonify({"error": f"Admin user '{admin_id}' not found"}), 404
        return jsonify(admin), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while updating admin user"}), 500
