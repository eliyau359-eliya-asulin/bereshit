"""
Bereshit Judaica — Flask API
Customer website  --\
                      -->  Flask API  -->  MongoDB
Admin dashboard   --/

Run (from the BERESHIT project root): python -m backend.app
"""
from flask import Flask, jsonify
from flask_cors import CORS

from backend.config import Config
from backend.db.mongo import get_db, create_indexes, ping
from backend.routes.products import bp as products_bp
from backend.routes.categories import bp as categories_bp
from backend.routes.orders import bp as orders_bp
from backend.routes.customers import bp as customers_bp
from backend.routes.promotions import bp as promotions_bp
from backend.routes.store_info import bp as store_info_bp


def create_app():
    Config.validate()

    app = Flask(__name__)
    CORS(app, origins=Config.CORS_ORIGINS)

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
        create_indexes(get_db())
    except Exception as e:
        app.logger.warning("Could not create indexes at startup (will retry on next request): %s", e)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
