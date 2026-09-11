from __future__ import annotations

import hashlib
import secrets
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash

from .db import get_db
from .integrations import barcode_product_lookup, tmdb_search
from .barcode_parser import best_match_score, rank_tmdb_results

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")

ROLE_LEVEL = {"viewer": 1, "editor": 2, "owner": 3}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _json_error(message: str, status: int = 400, **extra):
    return jsonify({"error": message, **extra}), status


def _library_role(db, library_id: int, user_id: int):
    library = db.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
    if not library:
        return None, None
    if int(library["owner_id"]) == int(user_id):
        return library, "owner"
    member = db.execute(
        "SELECT role FROM library_members WHERE library_id=? AND user_id=?",
        (library_id, user_id),
    ).fetchone()
    return (library, member["role"]) if member else (None, None)


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _json_error("Authentication required", 401)
        token = auth[7:].strip()
        token_hash = _token_hash(token)
        db = get_db()
        row = db.execute(
            """
            SELECT u.*
            FROM api_tokens t
            JOIN users u ON u.id=t.user_id
            WHERE t.token_hash=?
              AND t.auth_version=u.auth_version
              AND u.disabled=0
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return _json_error("Invalid or expired token", 401)
        g.api_user = row
        g.api_token_hash = token_hash
        db.execute(
            "UPDATE api_tokens SET last_used_at=CURRENT_TIMESTAMP WHERE token_hash=?",
            (token_hash,),
        )
        db.commit()
        return view(*args, **kwargs)
    return wrapped


def _movie_row(row):
    return {
        "id": row["id"],
        "library_id": row["library_id"],
        "shelf_id": row["shelf_id"],
        "tmdb_id": row["tmdb_id"],
        "title": row["title"],
        "year": int(row["year"]) if row["year"] and str(row["year"]).isdigit() else None,
        "overview": "",
        "poster_path": row["poster_path"],
        "runtime": None,
        "format": row["format"] or "Unknown",
        "upc": row["barcode"],
        "watched": False,
        "status": row["status"],
        "version": row["version"],
        "country": row["country"],
        "language": row["language"],
        "region": row["region"],
        "disc_count": row["disc_count"],
        "notes": row["notes"],
    }


def _accessible_library_ids(db, user_id: int):
    rows = db.execute(
        """
        SELECT id FROM libraries WHERE owner_id=?
        UNION
        SELECT library_id AS id FROM library_members WHERE user_id=?
        """,
        (user_id, user_id),
    ).fetchall()
    return [int(r["id"]) for r in rows]


@bp.get("/health")
def health():
    return jsonify({"name": "Homebuster", "api_version": "v1", "status": "ok"})


@bp.get("/status")
def status():
    return jsonify({
        "name": current_app.config.get("APP_NAME", "Homebuster"),
        "server_version": current_app.config.get("APP_VERSION", "0.3.12"),
        "api_version": "v1",
        "status": "ok",
    })


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)
    ).fetchone()
    if (
        not user
        or user["disabled"]
        or not check_password_hash(user["password_hash"], password)
    ):
        return _json_error("Invalid username or password", 401)
    token = secrets.token_urlsafe(32)
    db.execute(
        """
        INSERT INTO api_tokens(user_id, token_hash, auth_version, label)
        VALUES (?, ?, ?, ?)
        """,
        (
            user["id"],
            _token_hash(token),
            user["auth_version"],
            str(data.get("device_name") or "Android")[:80],
        ),
    )
    db.commit()
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": bool(user["is_admin"]),
        },
    })


@bp.post("/auth/logout")
@token_required
def logout():
    db = get_db()
    db.execute("DELETE FROM api_tokens WHERE token_hash=?", (g.api_token_hash,))
    db.commit()
    return "", 204


@bp.get("/me")
@token_required
def me():
    user = g.api_user
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "is_admin": bool(user["is_admin"]),
    })


@bp.get("/libraries")
@token_required
def libraries():
    db = get_db()
    rows = db.execute(
        """
        SELECT l.id, l.name, 'owner' AS role
        FROM libraries l WHERE l.owner_id=?
        UNION ALL
        SELECT l.id, l.name, lm.role
        FROM libraries l
        JOIN library_members lm ON lm.library_id=l.id
        WHERE lm.user_id=?
        ORDER BY name COLLATE NOCASE
        """,
        (g.api_user["id"], g.api_user["id"]),
    ).fetchall()
    return jsonify({"libraries": [dict(r) for r in rows]})


@bp.get("/shelves")
@token_required
def shelves():
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if not ids:
        return jsonify({"shelves": []})
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"SELECT id,library_id,name,description,sort_order FROM shelves WHERE library_id IN ({placeholders}) ORDER BY name COLLATE NOCASE",
        ids,
    ).fetchall()
    return jsonify({"shelves": [dict(r) for r in rows]})


@bp.get("/collections")
@token_required
def collections():
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if not ids:
        return jsonify({"collections": []})
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""
        SELECT c.id,c.library_id,c.name,COUNT(mc.movie_id) AS movie_count
        FROM collections c
        LEFT JOIN movie_collections mc ON mc.collection_id=c.id
        WHERE c.library_id IN ({placeholders})
        GROUP BY c.id,c.library_id,c.name
        ORDER BY c.name COLLATE NOCASE
        """,
        ids,
    ).fetchall()
    return jsonify({
        "collections": [
            {**dict(r), "description": ""}
            for r in rows
        ]
    })


@bp.get("/collections/<int:collection_id>/movies")
@token_required
def collection_movies(collection_id):
    db = get_db()
    collection = db.execute(
        "SELECT library_id FROM collections WHERE id=?", (collection_id,)
    ).fetchone()
    if not collection:
        return _json_error("Collection not found", 404)
    library, role = _library_role(db, collection["library_id"], g.api_user["id"])
    if not library:
        return _json_error("Collection not found", 404)
    rows = db.execute(
        """
        SELECT m.*
        FROM movies m
        JOIN movie_collections mc ON mc.movie_id=m.id
        WHERE mc.collection_id=? AND m.library_id=?
        ORDER BY m.title COLLATE NOCASE
        """,
        (collection_id, collection["library_id"]),
    ).fetchall()
    return jsonify({"movies": [_movie_row(r) for r in rows]})


@bp.get("/movies")
@token_required
def movies():
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if not ids:
        return jsonify({"movies": []})
    placeholders = ",".join("?" for _ in ids)
    args = list(ids)
    sql = f"SELECT m.* FROM movies m WHERE m.library_id IN ({placeholders})"
    query = (request.args.get("q") or "").strip()
    if query:
        sql += " AND (m.title LIKE ? OR m.year LIKE ? OR m.barcode LIKE ?)"
        needle = f"%{query}%"
        args.extend([needle, needle, needle])
    fmt = (request.args.get("format") or "").strip()
    if fmt:
        sql += " AND m.format=?"
        args.append(fmt)
    library_id = request.args.get("library_id", type=int)
    if library_id:
        if library_id not in ids:
            return _json_error("Library not found", 404)
        sql += " AND m.library_id=?"
        args.append(library_id)
    sql += " ORDER BY m.title COLLATE NOCASE"
    rows = db.execute(sql, args).fetchall()
    return jsonify({"movies": [_movie_row(r) for r in rows]})


@bp.get("/movies/<int:movie_id>")
@token_required
def movie_detail(movie_id):
    db = get_db()
    row = db.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
    if not row:
        return _json_error("Movie not found", 404)
    library, role = _library_role(db, row["library_id"], g.api_user["id"])
    if not library:
        return _json_error("Movie not found", 404)
    return jsonify({"movie": _movie_row(row)})


@bp.post("/movies")
@token_required
def add_movie():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return _json_error("Title is required")
    db = get_db()
    library_id = data.get("library_id")
    if library_id is None:
        row = db.execute(
            """
            SELECT id FROM libraries WHERE owner_id=? ORDER BY id LIMIT 1
            """,
            (g.api_user["id"],),
        ).fetchone()
        if row is None:
            row = db.execute(
                """
                SELECT library_id AS id FROM library_members
                WHERE user_id=? AND role='editor' ORDER BY library_id LIMIT 1
                """,
                (g.api_user["id"],),
            ).fetchone()
        if row is None:
            return _json_error("No editable Library is available", 403)
        library_id = row["id"]
    try:
        library_id = int(library_id)
    except (TypeError, ValueError):
        return _json_error("Invalid library_id")
    library, role = _library_role(db, library_id, g.api_user["id"])
    if not library or ROLE_LEVEL[role] < ROLE_LEVEL["editor"]:
        return _json_error("Library is not editable", 403)

    barcode = str(data.get("upc") or "").strip() or None
    disc_count = data.get("disc_count")
    if disc_count in (None, ""):
        disc_count = None
    else:
        try:
            disc_count = int(disc_count)
        except (TypeError, ValueError):
            return _json_error("disc_count must be a whole number")
        if disc_count < 1 or disc_count > 99:
            return _json_error("disc_count must be between 1 and 99")

    cur = db.execute(
        """
        INSERT INTO movies(
            library_id,barcode,title,year,format,poster_path,tmdb_id,status,version,language,region,disc_count,notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            library_id,
            barcode,
            title,
            str(data.get("year")) if data.get("year") is not None else None,
            str(data.get("format") or "Blu-ray"),
            data.get("poster_path"),
            data.get("tmdb_id"),
            "owned",
            str(data.get("version") or "").strip() or None,
            str(data.get("language") or "").strip() or None,
            str(data.get("region") or "").strip() or None,
            disc_count,
            None,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM movies WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"movie": _movie_row(row)}), 201


@bp.get("/loans")
@token_required
def loans():
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if not ids:
        return jsonify({"loans": []})
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""
        SELECT l.id,l.movie_id,m.title,l.borrower_name,l.loaned_date,l.returned_date,l.notes
        FROM loans l
        JOIN movies m ON m.id=l.movie_id
        WHERE l.library_id IN ({placeholders})
        ORDER BY l.returned_date IS NOT NULL, l.loaned_date DESC
        """,
        ids,
    ).fetchall()
    return jsonify({
        "loans": [
            {
                "id": r["id"],
                "movie_id": r["movie_id"],
                "title": r["title"],
                "borrower": r["borrower_name"],
                "loaned_at": r["loaned_date"],
                "returned_at": r["returned_date"],
                "notes": r["notes"] or "",
            }
            for r in rows
        ]
    })


@bp.get("/tmdb/search")
@token_required
def tmdb_lookup():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": []})
    try:
        return jsonify({"results": tmdb_search(query)})
    except Exception as exc:
        current_app.logger.warning("TMDb API lookup failed: %s", exc)
        return _json_error("TMDb lookup failed", 502)


def _barcode_tmdb_matches(product: dict) -> tuple[list[dict], list[dict]]:
    """Run progressively broader TMDb searches and keep the best candidates."""
    title = str(product.get("search_title") or product.get("product_title") or "").strip()
    fallback = str(product.get("fallback_title") or "").strip()
    year = product.get("search_year")

    queries: list[tuple[str, int | None]] = []
    for candidate in ((title, year), (title, None), (fallback, year), (fallback, None)):
        if not candidate[0]:
            continue
        key = (candidate[0].casefold(), candidate[1])
        if any((q.casefold(), y) == key for q, y in queries):
            continue
        queries.append(candidate)

    merged: dict[object, dict] = {}
    attempts: list[dict] = []
    for query_title, query_year in queries:
        raw = tmdb_search(query_title, query_year)
        ranked = rank_tmdb_results(query_title, query_year, raw)
        attempts.append({
            "title": query_title,
            "year": query_year,
            "results": len(ranked),
            "best_score": best_match_score(ranked),
        })
        for item in ranked:
            key = item.get("tmdb_id") or (item.get("title"), item.get("year"))
            current = merged.get(key)
            if current is None or int(item.get("match_score") or 0) > int(current.get("match_score") or 0):
                merged[key] = item
        # Exact/near-exact title matches score over this threshold.  Once one
        # exists, broader searches add noise and extra TMDb requests.
        if best_match_score(merged.values()) >= 105:
            break

    results = sorted(
        merged.values(),
        key=lambda item: (-int(item.get("match_score") or 0), str(item.get("title") or "").lower()),
    )
    return results[:20], attempts


@bp.get("/barcodes/<upc>")
@token_required
def barcode_lookup(upc):
    upc = "".join(ch for ch in upc if ch.isdigit())
    if len(upc) not in (8, 12, 13, 14):
        return _json_error("Unsupported barcode", 400)
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if ids:
        placeholders = ",".join("?" for _ in ids)
        existing = db.execute(
            f"SELECT * FROM movies WHERE library_id IN ({placeholders}) AND barcode=? ORDER BY id LIMIT 1",
            [*ids, upc],
        ).fetchone()
        if existing:
            return jsonify({"status": "owned", "movie": _movie_row(existing), "upc": upc})
    try:
        product = barcode_product_lookup(upc)
    except Exception as exc:
        current_app.logger.warning("Barcode lookup failed: %s", exc)
        return _json_error("Barcode provider failed", 502, provider_status="provider_error")
    if not product:
        return jsonify({"status": "not_found", "upc": upc}), 404
    search_title = (product.get("search_title") or product.get("product_title") or "").strip()
    search_year = product.get("search_year")
    try:
        matches, attempts = _barcode_tmdb_matches(product)
    except Exception as exc:
        current_app.logger.warning("TMDb barcode match lookup failed: %s", exc)
        matches, attempts = [], []
    return jsonify({
        "status": "product_match",
        "upc": upc,
        "product": product,
        "lookup": {
            "title": search_title,
            "fallback_title": product.get("fallback_title"),
            "year": search_year,
            "formats": product.get("detected_formats") or [],
            "format": product.get("detected_format"),
            "edition": product.get("detected_edition"),
            "language": product.get("detected_language"),
            "region": product.get("detected_region"),
            "disc_count": product.get("detected_disc_count"),
            "distributor": product.get("detected_distributor"),
            "attempts": attempts,
        },
        "best_match": matches[0] if matches else None,
        "tmdb_results": matches,
    })
