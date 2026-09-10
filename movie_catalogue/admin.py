from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from .db import backup_database, get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapped


@bp.get("/users")
@admin_required
def users():
    rows = get_db().execute(
        """
        SELECT u.*, (SELECT COUNT(*) FROM libraries l WHERE l.owner_id=u.id) AS owned_libraries
        FROM users u ORDER BY u.username COLLATE NOCASE
        """
    ).fetchall()
    return render_template("admin_users.html", users=rows)


@bp.post("/users/<username>/reset-password")
@admin_required
def reset_password(username):
    if username.lower() == current_user.username.lower():
        flash("Use the CLI to change your own admin password.", "warning")
        return redirect(url_for("admin.users"))
    password = request.form.get("new_password") or ""
    if len(password) < 10:
        flash("New password must be at least 10 characters.", "error")
    else:
        db = get_db(); target = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not target: abort(404)
        db.execute("UPDATE users SET password_hash=?,auth_version=auth_version+1 WHERE id=?", (generate_password_hash(password), target["id"])); db.commit()
        flash(f"Password reset for {username}. Existing sessions were invalidated.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<username>/toggle-disabled")
@admin_required
def toggle_disabled(username):
    if username.lower() == current_user.username.lower():
        flash("You cannot disable your own account.", "error")
        return redirect(url_for("admin.users"))
    db = get_db(); target = db.execute("SELECT id,disabled FROM users WHERE username=?", (username,)).fetchone()
    if not target: abort(404)
    disabled = 0 if target["disabled"] else 1
    db.execute("UPDATE users SET disabled=?,auth_version=auth_version+1 WHERE id=?", (disabled, target["id"])); db.commit()
    flash(f"{username} {'disabled' if disabled else 'enabled'}.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<username>/toggle-admin")
@admin_required
def toggle_admin(username):
    if username.lower() == current_user.username.lower():
        flash("You cannot change your own admin status here.", "error")
        return redirect(url_for("admin.users"))
    db = get_db(); target = db.execute("SELECT id,is_admin FROM users WHERE username=?", (username,)).fetchone()
    if not target: abort(404)
    db.execute("UPDATE users SET is_admin=? WHERE id=?", (0 if target["is_admin"] else 1, target["id"])); db.commit()
    flash("Admin status updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<username>/delete", methods=["GET", "POST"])
@admin_required
def delete_user(username):
    if username.lower() == current_user.username.lower():
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))
    db = get_db(); target = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not target: abort(404)
    libraries = db.execute(
        "SELECT l.*, (SELECT COUNT(*) FROM movies m WHERE m.library_id=l.id) AS movie_count FROM libraries l WHERE l.owner_id=? ORDER BY l.name COLLATE NOCASE",
        (target["id"],),
    ).fetchall()
    recipients = db.execute("SELECT id,username FROM users WHERE id<>? AND disabled=0 ORDER BY username COLLATE NOCASE", (target["id"],)).fetchall()
    if request.method == "POST":
        if request.form.get("confirm_username") != target["username"]:
            flash("Type the target username exactly.", "error")
            return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)
        admin_row = db.execute("SELECT password_hash FROM users WHERE id=?", (current_user.id,)).fetchone()
        if not check_password_hash(admin_row["password_hash"], request.form.get("admin_password") or ""):
            flash("Your admin password was incorrect.", "error")
            return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)
        if target["is_admin"]:
            admin_count = db.execute("SELECT COUNT(*) FROM users WHERE is_admin=1 AND disabled=0").fetchone()[0]
            if admin_count <= 1:
                flash("You cannot delete the only active site admin.", "error")
                return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)

        actions = []
        for library in libraries:
            action = request.form.get(f"library_action_{library['id']}") or ""
            if action == "delete":
                actions.append(("delete", library["id"], None))
            elif action.startswith("transfer:"):
                try: recipient_id = int(action.split(":",1)[1])
                except ValueError: recipient_id = -1
                valid = db.execute("SELECT id FROM users WHERE id=? AND id<>? AND disabled=0", (recipient_id, target["id"])).fetchone()
                if not valid:
                    flash(f"Choose a valid destination for Library {library['name']}.", "error")
                    return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)
                actions.append(("transfer", library["id"], recipient_id))
            else:
                flash(f"Choose transfer or delete for Library {library['name']}.", "error")
                return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)

        backup_database("before-user-delete")
        try:
            for action, library_id, recipient_id in actions:
                if action == "delete":
                    db.execute("DELETE FROM libraries WHERE id=?", (library_id,))
                else:
                    db.execute("DELETE FROM library_members WHERE library_id=? AND user_id=?", (library_id, recipient_id))
                    db.execute("UPDATE libraries SET owner_id=? WHERE id=?", (recipient_id, library_id))
            db.execute("DELETE FROM users WHERE id=?", (target["id"],))
            db.commit()
        except Exception:
            db.rollback(); raise
        flash(f"Deleted user {target['username']}. Library actions were completed first.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin_delete_user.html", target=target, libraries=libraries, recipients=recipients)
