"""
Bereshit Judaica — Flask API
Customer website  --\
                      -->  Flask API  -->  MongoDB
Admin dashboard   --/

Run (from the BERESHIT project root): python -m backend.app
"""
import os
import secrets

from flask import Flask, jsonify
from flask_cors import CORS

from backend.config import Config
from backend.db.mongo import get_db, create_indexes, bootstrap_counters, bootstrap_admin, ping
from backend.routes.products import bp as products_bp
from backend.routes.categories import bp as categories_bp
from backend.routes.orders import bp as orders_bp
from backend.routes.customers import bp as customers_bp
from backend.routes.promotions import bp as promotions_bp
from backend.routes.store_info import bp as store_info_bp
from backend.routes.auth import bp as auth_bp
from backend.routes.admin_users import bp as admin_users_bp
from backend.routes.cart import bp as cart_bp
from backend.routes.images import bp as images_bp


def create_app():
    Config.validate()

    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    # Every JSON endpoint's body is small (a product/order/etc document);
    # the one exception is image upload, capped again at 8MB inside
    # backend/images/processing.py. 9MB covers that plus multipart
    # overhead while still refusing a pathological giant body outright.
    app.config["MAX_CONTENT_LENGTH"] = 9 * 1024 * 1024
    # supports_credentials is required for the session cookie to be sent on
    # cross-origin requests (local dev, static site on one port + API on
    # another); origins must be an explicit list, never "*", per Config.
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(promotions_bp)
    app.register_blueprint(store_info_bp)

    @app.get("/api/health")
    def health():
        try:
            ping()
            return jsonify({"status": "ok", "database": "connected"}), 200
        except Exception as e:
            return jsonify({"status": "error", "database": "disconnected", "detail": str(e)}), 503

    @app.errorhandler(401)
    def unauthorized(_e):
        return jsonify({"error": "נדרשת התחברות", "code": "UNAUTHENTICATED"}), 401

    @app.errorhandler(403)
    def forbidden(_e):
        return jsonify({"error": "אין הרשאה מספקת", "code": "FORBIDDEN"}), 403

    @app.errorhandler(413)
    def payload_too_large(_e):
        return jsonify({"error": "גוף הבקשה גדול מדי", "code": "PAYLOAD_TOO_LARGE"}), 413

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify({"error": "Internal server error"}), 500

    try:
        db = get_db()
        create_indexes(db)
        bootstrap_counters(db)
        if bootstrap_admin(db):
            app.logger.info("Bootstrapped the first Super Admin account from ADMIN_BOOTSTRAP_EMAIL.")
    except Exception as e:
        app.logger.warning("Could not initialize indexes/counters at startup (will retry on next request): %s", e)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
