from __future__ import annotations

import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .db import backup_database, get_db
from .permissions import get_library_access, list_accessible_libraries, require_library_role

bp = Blueprint("libraries", __name__, url_prefix="/libraries")


@bp.get("")
@login_required
def index():
    libraries = list_accessible_libraries(current_user.id)
    return render_template("libraries.html", libraries=libraries)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Library name is required.", "error")
        else:
            db = get_db()
            cur = db.execute("INSERT INTO libraries (name, owner_id) VALUES (?, ?)", (name, current_user.id))
            db.commit()
            flash("Library created.", "success")
            return redirect(url_for("catalog.library_home", library_id=cur.lastrowid))
    return render_template("library_new.html")


@bp.get("/<int:library_id>/settings")
@login_required
@require_library_role("owner")
def settings(library_id, library, role):
    db = get_db()
    members = db.execute(
        """
        SELECT u.username, u.id AS user_id, lm.role
        FROM library_members lm JOIN users u ON u.id=lm.user_id
        WHERE lm.library_id=? ORDER BY u.username COLLATE NOCASE
        """,
        (library_id,),
    ).fetchall()
    counts = db.execute(
        "SELECT (SELECT COUNT(*) FROM movies WHERE library_id=?) AS movies, "
        "(SELECT COUNT(*) FROM shelves WHERE library_id=?) AS shelves, "
        "(SELECT COUNT(*) FROM loans WHERE library_id=? AND returned_date IS NULL) AS loans",
        (library_id, library_id, library_id),
    ).fetchone()
    return render_template("library_settings.html", library=library, role=role, members=members, counts=counts)


@bp.post("/<int:library_id>/rename")
@login_required
@require_library_role("owner")
def rename(library_id, library, role):
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Library name cannot be empty.", "error")
    else:
        db = get_db(); db.execute("UPDATE libraries SET name=? WHERE id=?", (name, library_id)); db.commit()
        flash("Library renamed.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/members")
@login_required
@require_library_role("owner")
def add_member(library_id, library, role):
    username = (request.form.get("username") or "").strip()
    member_role = request.form.get("role") or "viewer"
    if member_role not in {"viewer", "editor"}:
        member_role = "viewer"
    db = get_db()
    user = db.execute("SELECT id, disabled FROM users WHERE username=?", (username,)).fetchone()
    if not user or user["disabled"]:
        flash("No active user with that username exists.", "error")
    elif user["id"] == current_user.id:
        flash("You already own this Library.", "warning")
    else:
        try:
            db.execute("INSERT INTO library_members (library_id,user_id,role) VALUES (?,?,?)", (library_id, user["id"], member_role))
            db.commit(); flash(f"Added {username} as {member_role}.", "success")
        except sqlite3.IntegrityError:
            db.rollback(); flash("That user is already a member.", "warning")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/members/<username>/role")
@login_required
@require_library_role("owner")
def change_member_role(library_id, username, library, role):
    member_role = request.form.get("role") or "viewer"
    if member_role not in {"viewer", "editor"}:
        flash("Invalid role.", "error")
    else:
        db = get_db()
        db.execute(
            "UPDATE library_members SET role=? WHERE library_id=? AND user_id=(SELECT id FROM users WHERE username=?)",
            (member_role, library_id, username),
        )
        db.commit(); flash("Member role updated.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/members/<username>/remove")
@login_required
@require_library_role("owner")
def remove_member(library_id, username, library, role):
    db = get_db()
    db.execute(
        "DELETE FROM library_members WHERE library_id=? AND user_id=(SELECT id FROM users WHERE username=?)",
        (library_id, username),
    )
    db.commit(); flash(f"Removed {username} from the Library.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/transfer")
@login_required
@require_library_role("owner")
def transfer(library_id, library, role):
    username = (request.form.get("username") or "").strip()
    db = get_db()
    target = db.execute("SELECT id, disabled FROM users WHERE username=?", (username,)).fetchone()
    if not target or target["disabled"]:
        flash("Choose an active registered user.", "error")
    elif target["id"] == current_user.id:
        flash("You already own this Library.", "warning")
    else:
        db.execute("DELETE FROM library_members WHERE library_id=? AND user_id=?", (library_id, target["id"]))
        db.execute("UPDATE libraries SET owner_id=? WHERE id=?", (target["id"], library_id))
        db.execute(
            "INSERT OR REPLACE INTO library_members (library_id,user_id,role) VALUES (?,?, 'editor')",
            (library_id, current_user.id),
        )
        db.commit(); flash(f"Ownership transferred to {username}. You remain an Editor.", "success")
        return redirect(url_for("catalog.library_home", library_id=library_id))
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/clear")
@login_required
@require_library_role("owner")
def clear_movies(library_id, library, role):
    if request.form.get("confirmation") != "DELETE MY COLLECTION":
        flash('Type "DELETE MY COLLECTION" exactly to clear the Library.', "error")
        return redirect(url_for("libraries.settings", library_id=library_id))
    backup_database("before-clear")
    db = get_db(); db.execute("DELETE FROM movies WHERE library_id=?", (library_id,)); db.commit()
    flash("All movies were removed. A database backup was created first.", "success")
    return redirect(url_for("catalog.library_home", library_id=library_id))


@bp.post("/<int:library_id>/delete")
@login_required
@require_library_role("owner")
def delete(library_id, library, role):
    if request.form.get("confirmation") != library["name"]:
        flash("Type the Library name exactly to delete it.", "error")
        return redirect(url_for("libraries.settings", library_id=library_id))
    backup_database("before-library-delete")
    db = get_db(); db.execute("DELETE FROM libraries WHERE id=?", (library_id,)); db.commit()
    flash("Library deleted.", "success")
    return redirect(url_for("libraries.index"))
