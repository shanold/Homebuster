from __future__ import annotations

from functools import wraps

from flask import abort
from flask_login import current_user

from .db import get_db

ROLE_LEVEL = {"viewer": 1, "editor": 2, "owner": 3}


def get_library_access(library_id: int, user_id: int):
    db = get_db()
    library = db.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
    if not library:
        abort(404)
    if library["owner_id"] == user_id:
        return library, "owner"
    member = db.execute(
        "SELECT role FROM library_members WHERE library_id=? AND user_id=?",
        (library_id, user_id),
    ).fetchone()
    if not member:
        abort(403)
    return library, member["role"]


def require_library_role(minimum: str = "viewer"):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            library_id = kwargs.get("library_id")
            if library_id is None:
                abort(500)
            library, role = get_library_access(int(library_id), int(current_user.id))
            if ROLE_LEVEL[role] < ROLE_LEVEL[minimum]:
                abort(403)
            kwargs["library"] = library
            kwargs["role"] = role
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def list_accessible_libraries(user_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT l.*, 'owner' AS role
        FROM libraries l
        WHERE l.owner_id=?
        UNION ALL
        SELECT l.*, lm.role AS role
        FROM libraries l
        JOIN library_members lm ON lm.library_id=l.id
        WHERE lm.user_id=?
        ORDER BY name COLLATE NOCASE
        """,
        (user_id, user_id),
    ).fetchall()
