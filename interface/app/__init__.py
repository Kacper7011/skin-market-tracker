import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    from app.routes.main import main_bp
    from app.routes.api  import api_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp,  url_prefix="/api")
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_steam_status():
        from app.db import get_steam_auth_status
        try:
            return {"steam_auth": get_steam_auth_status()}
        except Exception:
            return {"steam_auth": None}

    return app