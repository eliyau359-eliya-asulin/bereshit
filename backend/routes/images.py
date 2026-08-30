from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from backend.models.schemas import ValidationError
from backend.services import images_service as svc
from backend.auth.decorators import require_admin

bp = Blueprint("images", __name__, url_prefix="/api/images")


@bp.get("/upload-authorize")
@require_admin("products:write")
def upload_authorize():
    """Called server-to-server by api/blob-upload-token.js (the small Node
    function that mints a short-lived, scoped Vercel Blob upload
    credential) — never called directly by the browser. That function
    forwards the browser's own admin session cookie here; if this
    returns anything but 200, it mints no token at all. This keeps
    authentication/authorization decided in exactly one place (the same
    session store + role/permission table every other admin route uses),
    instead of duplicating that logic in a second language."""
    return jsonify({"authorized": True}), 200


@bp.post("/process")
@require_admin("products:write")
def process_upload():
    """Second half of the client-direct-upload flow: the browser has
    already PUT the raw file straight to a temporary Blob path (see
    upload-authorize above and api/blob-upload-token.js), so this never
    receives the original file body at all — only a small JSON pointer
    to where it landed. That's what lets a full-size photo bypass
    Vercel's function body-size limit entirely, while every actual
    security control (auth, real image validation/decoding, resize,
    WebP conversion, thumbnail generation) still happens right here,
    server-side, exactly as it did with the old direct-multipart-upload
    endpoint this replaces."""
    data = request.get_json(silent=True) or {}
    try:
        result = svc.process_staged_image(data.get("pathname"))
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
