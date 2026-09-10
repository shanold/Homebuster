from __future__ import annotations

import re
import sqlite3

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


class User(UserMixin):
    def __init__(self, row):
        self.id = int(row["id"])
        self.username = row["username"]
        self.password_hash = row["password_hash"]
        self.is_admin = bool(row["is_admin"])
        self.disabled = bool(row["disabled"])
        self.auth_version = int(row["auth_version"])

    @property
    def is_active(self):
        return not self.disabled


@login_manager.user_loader
def load_user(user_id: str):
    row = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row or row["disabled"]:
        return None
    return User(row)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("libraries.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or row["disabled"] or not check_password_hash(row["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            user = User(row)
            login_user(user)
            session["auth_version"] = user.auth_version
            next_url = request.args.get("next")
            if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("libraries.index")
            return redirect(next_url)
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if not current_app.config.get("ALLOW_REGISTRATION", False):
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for("libraries.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not USERNAME_RE.fullmatch(username):
            flash("Username must be 3-32 characters using letters, numbers, _ or -.", "error")
        elif len(password) < 10:
            flash("Password must be at least 10 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.execute("INSERT INTO libraries (name, owner_id) VALUES ('My Movies', ?)", (cur.lastrowid,))
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That username is already in use.", "error")
            else:
                row = db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
                user = User(row)
                login_user(user)
                session["auth_version"] = user.auth_version
                flash("Account created. Welcome!", "success")
                return redirect(url_for("libraries.index"))
    return render_template("register.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
