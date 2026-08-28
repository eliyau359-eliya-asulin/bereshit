from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import images_service as svc
from backend.auth.decorators import require_admin

bp = Blueprint("images", __name__, url_prefix="/api/images")


@bp.post("/upload")
@require_admin("products:write")
def upload_image():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "לא נשלח קובץ תחת השדה 'file'"}), 400
    try:
        raw_bytes = file.read()
        result = svc.upload_product_image(raw_bytes)
        return jsonify(result), 201
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e), "code": "STORAGE_NOT_CONFIGURED"}), 503
    except PyMongoError:
        return jsonify({"error": "Database error while uploading image"}), 500


@bp.delete("")
@require_admin("products:write")
def delete_image():
    data = request.get_json(silent=True) or {}
    try:
        result = svc.delete_product_image(data.get("url"))
        return jsonify(result), 200
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except PyMongoError:
        return jsonify({"error": "Database error while deleting image"}), 500
