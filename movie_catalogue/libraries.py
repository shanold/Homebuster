from __future__ import annotations

import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .db import backup_database, get_db
from .permissions import get_library_access, list_accessible_libraries, require_library_role

bp = Blueprint("libraries", __name__, url_prefix="/libraries")

LIBRARY_DEFAULT_MEDIA_TYPES = {"movie", "tv", "collection"}

def normalize_library_default_media_type(value):
    value = str(value or "movie").strip().lower()
    return value if value in LIBRARY_DEFAULT_MEDIA_TYPES else "movie"


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
        default_media_type = normalize_library_default_media_type(request.form.get("default_media_type"))
        if not name:
            flash("Library name is required.", "error")
        else:
            db = get_db()
            cur = db.execute(
                "INSERT INTO libraries (name, owner_id, default_media_type) VALUES (?, ?, ?)",
                (name, current_user.id, default_media_type),
            )
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
        "SELECT (SELECT COUNT(*) FROM movies WHERE library_id=? AND parent_box_set_id IS NULL) AS movies, "
        "(SELECT COUNT(*) FROM box_sets WHERE library_id=?) AS box_sets, "
        "(SELECT COUNT(*) FROM movies WHERE library_id=? AND parent_box_set_id IS NOT NULL) AS contained_films, "
        "(SELECT COUNT(*) FROM shelves WHERE library_id=?) AS shelves, "
        "((SELECT COUNT(*) FROM loans WHERE library_id=? AND returned_date IS NULL) + "
        " (SELECT COUNT(*) FROM box_set_loans WHERE library_id=? AND returned_date IS NULL)) AS loans",
        (library_id, library_id, library_id, library_id, library_id, library_id),
    ).fetchone()
    return render_template("library_settings.html", library=library, role=role, members=members, counts=counts)


@bp.post("/<int:library_id>/settings/default-media-type")
@login_required
@require_library_role("owner")
def set_default_media_type(library_id, library, role):
    default_media_type = normalize_library_default_media_type(request.form.get("default_media_type"))
    db = get_db()
    db.execute("UPDATE libraries SET default_media_type=? WHERE id=?", (default_media_type, library_id))
    db.commit()
    flash("Library default content type updated.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/settings/smart-collections")
@login_required
@require_library_role("owner")
def set_smart_collections(library_id, library, role):
    db = get_db()
    db.execute("UPDATE libraries SET smart_collections_enabled=? WHERE id=?", (1 if request.form.get("smart_collections_enabled") else 0, library_id))
    db.commit()
    flash("Smart Collections setting updated.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))


@bp.post("/<int:library_id>/settings/box-set-members")
@login_required
@require_library_role("editor")
def set_box_set_members_visibility(library_id, library, role):
    db = get_db()
    db.execute("UPDATE libraries SET show_box_set_members=? WHERE id=?", (1 if request.form.get("show_box_set_members") else 0, library_id))
    db.commit()
    flash("Box-set browsing preference updated.", "success")
    if role == "owner":
        return redirect(url_for("libraries.settings", library_id=library_id))
    return redirect(url_for("catalog.library_home", library_id=library_id))


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
    db = get_db(); db.execute("DELETE FROM movies WHERE library_id=?", (library_id,)); db.execute("DELETE FROM box_sets WHERE library_id=?", (library_id,)); db.commit()
    flash("All titles and movie box sets were removed. A database backup was created first.", "success")
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

@bp.get("/<int:library_id>/tv-move-review")
@login_required
@require_library_role("owner")
def tv_move_review(library_id, library, role):
    db = get_db()
    tv_items = db.execute(
        """SELECT m.id,m.title,m.year,m.poster_path,m.shelf_id,s.name AS shelf_name
           FROM movies m LEFT JOIN shelves s ON s.id=m.shelf_id
           WHERE m.library_id=? AND m.media_type='tv' AND m.parent_box_set_id IS NULL
           ORDER BY m.title COLLATE NOCASE,m.year,m.id""", (library_id,)
    ).fetchall()
    destinations = db.execute(
        "SELECT id,name FROM libraries WHERE owner_id=? AND id<>? ORDER BY name COLLATE NOCASE",
        (current_user.id, library_id),
    ).fetchall()
    return render_template("tv_move_review.html", library=library, tv_items=tv_items, destinations=destinations)


@bp.post("/<int:library_id>/tv-move-review")
@login_required
@require_library_role("owner")
def tv_move_apply(library_id, library, role):
    db = get_db()
    try:
        destination_library_id = int(request.form.get("destination_library_id") or 0)
    except ValueError:
        destination_library_id = 0
    destination = db.execute(
        "SELECT id,name FROM libraries WHERE id=? AND owner_id=? AND id<>?",
        (destination_library_id, current_user.id, library_id),
    ).fetchone()
    if not destination:
        flash("Choose one of your other Libraries as the destination.", "error")
        return redirect(url_for("libraries.tv_move_review", library_id=library_id))

    selected_movie_ids = []
    for raw in request.form.getlist("movie_id"):
        try: selected_movie_ids.append(int(raw))
        except ValueError: pass
    if not selected_movie_ids:
        flash("Select at least one detected TV show to move.", "warning")
        return redirect(url_for("libraries.tv_move_review", library_id=library_id))

    placeholders = ",".join("?" for _ in selected_movie_ids)
    rows = db.execute(
        f"""SELECT m.id,m.shelf_id,s.name AS shelf_name,s.description,s.sort_order
            FROM movies m LEFT JOIN shelves s ON s.id=m.shelf_id
            WHERE m.library_id=? AND m.media_type='tv' AND m.id IN ({placeholders})""",
        (library_id, *selected_movie_ids),
    ).fetchall()
    moved = 0
    for item in rows:
        destination_shelf_id = None
        if item["shelf_id"] and item["shelf_name"]:
            existing = db.execute(
                "SELECT id FROM shelves WHERE library_id=? AND name=? COLLATE NOCASE",
                (destination_library_id, item["shelf_name"]),
            ).fetchone()
            if existing:
                destination_shelf_id = existing["id"]
            else:
                cur = db.execute(
                    "INSERT INTO shelves (library_id,name,description,sort_order) VALUES (?,?,?,?)",
                    (destination_library_id, item["shelf_name"], item["description"], item["sort_order"]),
                )
                destination_shelf_id = cur.lastrowid
        db.execute("UPDATE movies SET library_id=?, shelf_id=? WHERE id=? AND library_id=? AND media_type='tv'",
                   (destination_library_id, destination_shelf_id, item["id"], library_id))
        # Keep the title's loans/history internally consistent with its new Library.
        db.execute("UPDATE loans SET library_id=? WHERE movie_id=? AND library_id=?",
                   (destination_library_id, item["id"], library_id))
        moved += 1
    db.commit()
    flash(f"Moved {moved} selected TV {'title' if moved == 1 else 'titles'} to {destination['name']}. Shelf locations were preserved.", "success")
    return redirect(url_for("libraries.tv_move_review", library_id=library_id))
