from __future__ import annotations

import hashlib
import secrets
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash

from .db import get_db
from .box_set_service import (BoxSetLoanConflict, create_box_set, get_box_set, get_box_set_members, box_set_effective_state, member_effective_state, loan_box_set, return_box_set, loan_box_set_member, return_box_set_member)
from .integrations import barcode_product_lookup, tmdb_search, tmdb_collection_search, tmdb_collection_details
from .barcode_parser import (
    best_match_score,
    generate_movie_title_candidates,
    search_ready_movie_title_candidates,
    search_ready_title_candidates,
    infer_copy_metadata_from_legacy_title,
    rank_tmdb_results,
    movie_box_set_title_candidates,
)

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")

ROLE_LEVEL = {"viewer": 1, "editor": 2, "owner": 3}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mobile_poster_url(poster_path):
    if not poster_path:
        return None
    value = str(poster_path).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    size = current_app.config.get("TMDB_POSTER_SIZE", "w342")
    return f"https://image.tmdb.org/t/p/{size}{value if value.startswith('/') else '/' + value}"


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
        "media_type": row["media_type"] if "media_type" in row.keys() else "movie",
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


def _box_set_row(db, row, include_members=True):
    state = box_set_effective_state(db, row["id"])
    data = {
        "id": row["id"], "library_id": row["library_id"], "title": row["title"],
        "tmdb_collection_id": row["tmdb_collection_id"], "poster_path": _mobile_poster_url(row["poster_path"]),
        "format": row["format"], "upc": row["barcode"], "barcode": row["barcode"],
        "version": row["version"], "country": row["country"], "language": row["language"],
        "region": row["region"], "disc_count": row["disc_count"], "notes": row["notes"],
        "shelf_id": row["shelf_id"], "status": row["status"], "loan_state": state["state"],
    }
    if include_members:
        data["members"] = []
        for member in get_box_set_members(db, row["id"]):
            effective = member_effective_state(db, member["id"])
            data["members"].append({"id":member["id"],"tmdb_id":member["tmdb_id"],"title":member["title"],"year":int(member["year"]) if member["year"] and str(member["year"]).isdigit() else None,"poster_path":_mobile_poster_url(member["poster_path"]),"position":member["position"],"loan_state":effective["state"]})
    return data


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
    media_type = "tv" if str(data.get("media_type") or "movie").strip().lower() == "tv" else "movie"
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
            library_id,barcode,title,year,format,poster_path,tmdb_id,media_type,status,version,language,region,disc_count,notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            library_id,
            barcode,
            title,
            str(data.get("year")) if data.get("year") is not None else None,
            str(data.get("format") or "Blu-ray"),
            _mobile_poster_url(data.get("poster_path")),
            data.get("tmdb_id"),
            media_type,
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
    media_type = "tv" if (request.args.get("media_type") or "movie").strip().lower() == "tv" else "movie"
    try:
        return jsonify({"results": tmdb_search(query, media_type=media_type)})
    except Exception as exc:
        current_app.logger.warning("TMDb API lookup failed: %s", exc)
        return _json_error("TMDb lookup failed", 502)


def _barcode_tmdb_matches(product: dict, media_type: str = "movie") -> tuple[list[dict], list[dict]]:
    """Use the same candidate generator as web Identify/Repair for scanner TMDb searches."""
    raw_title = str(product.get("product_title") or "").strip()
    year = product.get("search_year")

    queries: list[tuple[str, int | None]] = []
    candidates = search_ready_title_candidates(raw_title, media_type=media_type)
    for value in (product.get("search_title"), *candidates, product.get("fallback_title")):
        title = str(value or "").strip()
        if not title:
            continue
        key = (title.casefold(), year)
        if any((q.casefold(), y) == key for q, y in queries):
            continue
        queries.append((title, year))

    merged: dict[object, dict] = {}
    attempts: list[dict] = []
    for query_title, query_year in queries[:3]:
        raw = tmdb_search(query_title, query_year, media_type=media_type)
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
        if best_match_score(merged.values()) >= 105:
            break

    results = sorted(
        merged.values(),
        key=lambda item: (-int(item.get("match_score") or 0), str(item.get("title") or "").lower()),
    )[:20]
    for item in results:
        item["copy_metadata"] = infer_copy_metadata_from_legacy_title(raw_title, item.get("title") or "", media_type=media_type)
        item["media_type"] = media_type
    return results, attempts


@bp.get("/barcodes/<upc>")
@token_required
def barcode_lookup(upc):
    requested_type = (request.args.get("media_type") or "movie").strip().lower()
    if requested_type not in {"movie", "tv", "collection"}:
        return _json_error("media_type must be movie, tv, or collection", 400)
    media_type = requested_type
    upc = "".join(ch for ch in upc if ch.isdigit())
    if len(upc) not in (8, 12, 13, 14):
        return _json_error("Unsupported barcode", 400)
    db = get_db()
    ids = _accessible_library_ids(db, g.api_user["id"])
    if ids:
        placeholders = ",".join("?" for _ in ids)
        if media_type == "collection":
            existing_box = db.execute(f"SELECT * FROM box_sets WHERE library_id IN ({placeholders}) AND barcode=? ORDER BY id LIMIT 1", [*ids, upc]).fetchone()
            if existing_box:
                return jsonify({"status":"owned","box_set":_box_set_row(db,existing_box),"upc":upc,"media_type":"collection"})
        else:
            existing = db.execute(f"SELECT * FROM movies WHERE library_id IN ({placeholders}) AND barcode=? ORDER BY id LIMIT 1", [*ids, upc]).fetchone()
            if existing:
                return jsonify({"status": "owned", "movie": _movie_row(existing), "upc": upc})
    try:
        product = barcode_product_lookup(upc)
    except Exception as exc:
        current_app.logger.warning("Barcode lookup failed: %s", exc)
        return _json_error("Barcode provider failed", 502, provider_status="provider_error")
    if not product:
        return jsonify({
            "status": "provider_not_found",
            "upc": upc,
            "provider_status": "not_found",
            "message": "UPCitemdb did not find a product for this barcode",
            "product": None,
            "lookup": None,
            "best_match": None,
            "tmdb_results": [],
        })
    if media_type == "collection":
        raw_title = str(product.get("product_title") or "").strip()
        candidates = movie_box_set_title_candidates(raw_title)
        attempts=[]; merged={}
        try:
            for query_title in candidates[:3]:
                results = tmdb_collection_search(query_title)
                attempts.append({"title":query_title,"results":len(results)})
                for item in results:
                    merged[item.get("id") or item.get("title")] = item
                if results:
                    break
        except Exception as exc:
            current_app.logger.warning("TMDb Collection barcode lookup failed: %s", exc)
        results=list(merged.values())[:20]
        return jsonify({"status":"product_match","upc":upc,"product":product,"lookup":{"title":attempts[-1]["title"] if attempts else raw_title,"attempts":attempts,"format":product.get("detected_format"),"formats":product.get("detected_formats") or [],"edition":product.get("detected_edition"),"language":product.get("detected_language"),"region":product.get("detected_region"),"disc_count":product.get("detected_disc_count")},"best_match":results[0] if results else None,"media_type":"collection","tmdb_results":results})

    search_title = (product.get("search_title") or product.get("product_title") or "").strip()
    search_year = product.get("search_year")
    try:
        matches, attempts = _barcode_tmdb_matches(product, media_type=media_type)
    except Exception as exc:
        current_app.logger.warning("TMDb barcode match lookup failed: %s", exc)
        matches, attempts = [], []
    best_metadata = (matches[0].get("copy_metadata") if matches else None) or {}
    return jsonify({
        "status": "product_match",
        "upc": upc,
        "product": product,
        "lookup": {
            "title": attempts[-1]["title"] if attempts else search_title,
            "fallback_title": product.get("fallback_title"),
            "year": search_year,
            "formats": list(best_metadata.get("formats") or product.get("detected_formats") or []),
            "format": best_metadata.get("format") or product.get("detected_format"),
            "edition": best_metadata.get("edition") or product.get("detected_edition"),
            "language": best_metadata.get("language") or product.get("detected_language"),
            "region": best_metadata.get("region") or product.get("detected_region"),
            "disc_count": best_metadata.get("disc_count") or product.get("detected_disc_count"),
            "distributor": product.get("detected_distributor"),
            "category": product.get("detected_category"),
            "attempts": attempts,
        },
        "best_match": matches[0] if matches else None,
        "media_type": media_type,
        "tmdb_results": matches,
    })


@bp.get("/tmdb/collections/search")
@token_required
def tmdb_collection_lookup():
    query=(request.args.get("q") or "").strip()
    if not query: return jsonify({"results":[]})
    try: return jsonify({"results":tmdb_collection_search(query)})
    except Exception as exc:
        current_app.logger.warning("TMDb Collection lookup failed: %s",exc)
        return _json_error("TMDb Collection lookup failed",502)

@bp.get("/tmdb/collections/<int:collection_id>")
@token_required
def tmdb_collection_detail(collection_id):
    try: details=tmdb_collection_details(collection_id)
    except Exception as exc:
        current_app.logger.warning("TMDb Collection detail failed: %s",exc); return _json_error("TMDb Collection lookup failed",502)
    if not details: return _json_error("Collection not found",404)
    return jsonify({"collection":details})

@bp.get("/box-sets")
@token_required
def box_sets_list():
    db=get_db(); ids=_accessible_library_ids(db,g.api_user["id"])
    if not ids: return jsonify({"box_sets":[]})
    library_id=request.args.get("library_id",type=int)
    if library_id is not None and library_id not in ids: return _json_error("Library not found",404)
    target=[library_id] if library_id is not None else ids
    ph=','.join('?' for _ in target); q=(request.args.get('q') or '').strip(); params=list(target)
    sql=f"SELECT DISTINCT bs.* FROM box_sets bs LEFT JOIN box_set_members bsm ON bsm.box_set_id=bs.id WHERE bs.library_id IN ({ph})"
    if q:
        sql+=" AND (bs.title LIKE ? OR bs.barcode LIKE ? OR bsm.title LIKE ?)"; needle=f"%{q}%"; params.extend([needle,needle,needle])
    sql+=" ORDER BY bs.title COLLATE NOCASE"
    return jsonify({"box_sets":[_box_set_row(db,r) for r in db.execute(sql,params).fetchall()]})

@bp.get("/box-sets/<int:box_set_id>")
@token_required
def box_set_detail_api(box_set_id):
    db=get_db(); row=db.execute("SELECT * FROM box_sets WHERE id=?",(box_set_id,)).fetchone()
    if not row: return _json_error("Box set not found",404)
    library,role=_library_role(db,row["library_id"],g.api_user["id"])
    if not library: return _json_error("Box set not found",404)
    return jsonify({"box_set":_box_set_row(db,row)})

@bp.post("/box-sets")
@token_required
def add_box_set_api():
    data=request.get_json(silent=True) or {}; db=get_db(); library_id=data.get("library_id")
    try: library_id=int(library_id)
    except (TypeError,ValueError): return _json_error("library_id is required")
    library,role=_library_role(db,library_id,g.api_user["id"])
    if not library or ROLE_LEVEL[role]<ROLE_LEVEL["editor"]: return _json_error("Library is not editable",403)
    physical={k:data.get(k) for k in ("barcode","title","tmdb_collection_id","poster_path","format","version","country","language","region","disc_count","notes","shelf_id","status")}
    physical["poster_path"]=_mobile_poster_url(physical.get("poster_path")); physical["status"]=physical.get("status") or "owned"
    if physical.get("shelf_id") not in (None, ""):
        try: shelf_id=int(physical["shelf_id"])
        except (TypeError,ValueError): return _json_error("Invalid shelf_id")
        if not db.execute("SELECT 1 FROM shelves WHERE id=? AND library_id=?",(shelf_id,library_id)).fetchone():
            return _json_error("Shelf does not belong to this Library",400)
        physical["shelf_id"]=shelf_id
    members=[]
    for i,m in enumerate(data.get("members") or []):
        members.append({"tmdb_id":m.get("tmdb_id"),"title":m.get("title"),"year":m.get("year"),"poster_path":_mobile_poster_url(m.get("poster_path")),"position":m.get("position",i)})
    try: box_id=create_box_set(db,library_id,physical,members)
    except Exception as exc: return _json_error(str(exc),400)
    row=db.execute("SELECT * FROM box_sets WHERE id=?",(box_id,)).fetchone(); return jsonify({"box_set":_box_set_row(db,row)}),201

def _api_box_access(box_set_id,minimum="viewer"):
    db=get_db(); row=db.execute("SELECT * FROM box_sets WHERE id=?",(box_set_id,)).fetchone()
    if not row: return db,None,None,_json_error("Box set not found",404)
    library,role=_library_role(db,row["library_id"],g.api_user["id"])
    if not library: return db,row,None,_json_error("Box set not found",404)
    if ROLE_LEVEL[role]<ROLE_LEVEL[minimum]: return db,row,role,_json_error("Library is not editable",403)
    return db,row,role,None

@bp.post("/box-sets/<int:box_set_id>/loan")
@token_required
def loan_box_set_api(box_set_id):
    db,row,role,error=_api_box_access(box_set_id,"editor")
    if error:return error
    data=request.get_json(silent=True) or {}
    try: loan_box_set(db,row["library_id"],box_set_id,data.get("borrower_name"),data.get("phone"),data.get("loaned_date"),data.get("notes"))
    except BoxSetLoanConflict as exc:return _json_error(str(exc),409)
    except ValueError as exc:return _json_error(str(exc),400)
    return jsonify({"box_set":_box_set_row(db,row)})

@bp.post("/box-sets/<int:box_set_id>/return")
@token_required
def return_box_set_api(box_set_id):
    db,row,role,error=_api_box_access(box_set_id,"editor")
    if error:return error
    data=request.get_json(silent=True) or {}; return_box_set(db,row["library_id"],box_set_id,data.get("returned_date")); return jsonify({"box_set":_box_set_row(db,row)})

@bp.post("/box-set-members/<int:member_id>/loan")
@token_required
def loan_box_set_member_api(member_id):
    db=get_db(); member=db.execute("SELECT bsm.*,bs.library_id FROM box_set_members bsm JOIN box_sets bs ON bs.id=bsm.box_set_id WHERE bsm.id=?",(member_id,)).fetchone()
    if not member:return _json_error("Contained film not found",404)
    library,role=_library_role(db,member["library_id"],g.api_user["id"])
    if not library or ROLE_LEVEL[role]<ROLE_LEVEL["editor"]:return _json_error("Library is not editable",403)
    data=request.get_json(silent=True) or {}
    try:loan_box_set_member(db,member["library_id"],member_id,data.get("borrower_name"),data.get("phone"),data.get("loaned_date"),data.get("notes"))
    except BoxSetLoanConflict as exc:return _json_error(str(exc),409)
    except ValueError as exc:return _json_error(str(exc),400)
    return jsonify({"member_id":member_id,"loan_state":member_effective_state(db,member_id)["state"]})

@bp.post("/box-set-members/<int:member_id>/return")
@token_required
def return_box_set_member_api(member_id):
    db=get_db(); member=db.execute("SELECT bsm.*,bs.library_id FROM box_set_members bsm JOIN box_sets bs ON bs.id=bsm.box_set_id WHERE bsm.id=?",(member_id,)).fetchone()
    if not member:return _json_error("Contained film not found",404)
    library,role=_library_role(db,member["library_id"],g.api_user["id"])
    if not library or ROLE_LEVEL[role]<ROLE_LEVEL["editor"]:return _json_error("Library is not editable",403)
    data=request.get_json(silent=True) or {}; return_box_set_member(db,member["library_id"],member_id,data.get("returned_date")); return jsonify({"member_id":member_id,"loan_state":member_effective_state(db,member_id)["state"]})
