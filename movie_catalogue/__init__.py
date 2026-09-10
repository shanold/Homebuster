from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, redirect, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFProtect

from .config import Config

csrf = CSRFProtect()


def _ensure_secret_key(app: Flask) -> None:
    if app.config.get("SECRET_KEY"):
        return
    db_path = Path(app.config["DATABASE_PATH"])
    secret_file = db_path.parent / ".secret_key"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        secret = secret_file.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_urlsafe(48)
        secret_file.write_text(secret, encoding="utf-8")
    app.config["SECRET_KEY"] = secret


def create_app(test_config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    _ensure_secret_key(app)

    from . import db
    db.init_app(app)

    from .auth import bp as auth_bp, login_manager
    login_manager.init_app(app)
    csrf.init_app(app)

    from .libraries import bp as libraries_bp
    from .catalog import bp as catalog_bp
    from .admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(libraries_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def validate_auth_version():
        if current_user.is_authenticated:
            if session.get("auth_version") != current_user.auth_version:
                logout_user()
                session.clear()

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("libraries.index"))
        return redirect(url_for("auth.login"))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    with app.app_context():
        db.initialize_database()

    return app
