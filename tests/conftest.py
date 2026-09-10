import os
import sqlite3
import tempfile
import pytest

from movie_catalogue import create_app


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "DATABASE_PATH": str(db_path),
        "SECRET_KEY": "test-secret",
        "ALLOW_REGISTRATION": True,
        "TMDB_API_KEY": "",
    })
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(app, username, password="verysecurepass", *, admin=False):
    from movie_catalogue.db import get_db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = get_db()
        cur = db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), 1 if admin else 0),
        )
        user_id = cur.lastrowid
        lib = db.execute(
            "INSERT INTO libraries (name, owner_id) VALUES (?, ?)",
            ("My Movies", user_id),
        )
        library_id = lib.lastrowid
        db.commit()
        return user_id, library_id


def login(client, username, password="verysecurepass"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)
