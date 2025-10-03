from flask import Flask, jsonify
from app.routes.user_routes import user_blueprint
from app.routes.product_routes import product_blueprint

def create_app():
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(user_blueprint)
    app.register_blueprint(product_blueprint)


    @app.get("/status")
    def status():
        return jsonify(status="ok"), 200

    return app

