from __future__ import annotations

import csv
import io
from datetime import date

import requests
from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .db import get_db
from .permissions import require_library_role
from .barcode_parser import (
    generate_movie_title_candidates,
    search_ready_movie_title_candidates,
    search_ready_title_candidates,
    high_confidence_tmdb_match,
    infer_legacy_title_year,
    infer_copy_metadata_from_legacy_title,
    parse_barcode_product_title,
)

bp = Blueprint("catalog", __name__)

MAX_MATCH_SEARCHES = 3
BULK_REPAIR_BATCH_SIZE = 8

MOVIE_FIELDS = [
    "barcode", "title", "year", "format", "poster_path", "tmdb_id", "media_type", "status",
    "version", "country", "language", "region", "disc_count", "notes", "shelf_id",
]



def _group_movie_rows(rows):
    # Group identity is (movie.get("media_type") or "movie", movie.get("tmdb_id")) when TMDb-backed.
    """Group physical copies for catalogue display without merging database rows."""
    groups = []
    by_key = {}
    for raw in rows:
        movie = dict(raw)
        key = ("tmdb", movie.get("media_type") or "movie", movie.get("tmdb_id")) if movie.get("tmdb_id") else ("copy", movie.get("id"))
        group = by_key.get(key)
        if group is None:
            group = dict(movie)
            group["copies"] = [movie]
            group["copy_count"] = 1
            group["formats"] = [movie.get("format")] if movie.get("format") else []
            by_key[key] = group
            groups.append(group)
        else:
            group["copies"].append(movie)
            group["copy_count"] += 1
            if movie.get("format") and movie.get("format") not in group["formats"]:
                group["formats"].append(movie.get("format"))
            if not group.get("poster_path") and movie.get("poster_path"):
                group["poster_path"] = movie.get("poster_path")
            if not group.get("active_loan_id") and movie.get("active_loan_id"):
                group["active_loan_id"] = movie.get("active_loan_id")
                group["borrower_name"] = movie.get("borrower_name")
    return groups



def _media_type(value):
    return "tv" if str(value or "").strip().lower() == "tv" else "movie"


def _match_queries_for_movie(movie):
    """Build multiple safe TMDb search candidates for an existing movie.

    The stored title is never mutated by candidate generation. A structured
    year already stored on the movie wins over a year parsed from legacy text.
    """
    raw_title = (movie["title"] or "").strip()
    parsed = parse_barcode_product_title(raw_title)
    media_type = _media_type(movie["media_type"] if "media_type" in movie.keys() else "movie")
    query_titles = search_ready_title_candidates(raw_title, media_type=media_type) or [raw_title]
    query_year = movie["year"] if movie["year"] not in (None, "") else infer_legacy_title_year(raw_title)
    return query_titles, query_year


def _tmdb_search_candidates(query_titles, year=None, max_searches=None, media_type="movie"):
    """Search candidate titles and merge TMDb movies without duplicate IDs."""
    merged = []
    seen_ids = set()
    searched = 0
    for title in query_titles:
        if not title:
            continue
        if max_searches is not None and searched >= max_searches:
            break
        searched += 1
        for item in _tmdb_search(title, year, media_type=media_type):
            tmdb_id = item.get("id")
            key = ("id", tmdb_id) if tmdb_id is not None else ("title", item.get("title"), item.get("release_date"))
            if key in seen_ids:
                continue
            seen_ids.add(key)
            merged.append(item)
    return merged


def _normalized_tmdb_matches(items):
    normalized = []
    for item in items:
        date = item.get("release_date") or ""
        normalized.append({
            "tmdb_id": item.get("id"),
            "title": item.get("title") or item.get("original_title") or "",
            "year": int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None,
        })
    return normalized


def _find_high_confidence_match(query_titles, query_year, search_cache, media_type="movie"):
    """Search at most MAX_MATCH_SEARCHES candidates, stopping on a decisive match."""
    merged = []
    seen_ids = set()
    searched_titles = []
    for title in query_titles[:MAX_MATCH_SEARCHES]:
        key = (_media_type(media_type), (title or "").casefold(), str(query_year or ""))
        if key not in search_cache:
            search_cache[key] = _tmdb_search(title, query_year, media_type=media_type)
        searched_titles.append(title)
        for item in search_cache[key]:
            item_key = item.get("id") or (item.get("title"), item.get("release_date"))
            if item_key in seen_ids:
                continue
            seen_ids.add(item_key)
            merged.append(item)
        choice = high_confidence_tmdb_match(searched_titles, query_year, _normalized_tmdb_matches(merged))
        if choice:
            return choice
    return None


def _metadata_value_is_blank(value, *, unknown=False):
    if value is None or str(value).strip() == "":
        return True
    return unknown and str(value).strip().casefold() == "unknown"


def _copy_metadata_fill_values(movie, raw_title, canonical_title, media_type="movie"):
    """Fill only missing copy metadata using the TMDb-confirmed title as anchor."""
    inferred = infer_copy_metadata_from_legacy_title(raw_title, canonical_title, media_type=media_type)
    values = {
        "format": movie["format"],
        "version": movie["version"],
        "language": movie["language"],
        "region": movie["region"],
        "disc_count": movie["disc_count"],
    }
    if _metadata_value_is_blank(values["format"], unknown=True) and inferred.get("format"):
        values["format"] = inferred["format"]
    if _metadata_value_is_blank(values["version"]) and inferred.get("edition"):
        values["version"] = inferred["edition"]
    if _metadata_value_is_blank(values["language"]) and inferred.get("language"):
        values["language"] = inferred["language"]
    if _metadata_value_is_blank(values["region"]) and inferred.get("region"):
        values["region"] = inferred["region"]
    if values["disc_count"] in (None, "") and inferred.get("disc_count"):
        values["disc_count"] = inferred["disc_count"]
    changed = any(values[field] != movie[field] for field in values)
    return values, inferred, changed


def _apply_identified_movie(db, movie, data, tmdb_id, media_type=None):
    media_type = _media_type(media_type or movie["media_type"] if "media_type" in movie.keys() else "movie")
    canonical_title = data.get("title") or movie["title"]
    values, inferred, metadata_changed = _copy_metadata_fill_values(movie, movie["title"], canonical_title, media_type=media_type)
    poster = _tmdb_poster_url(data.get("poster_path") or movie["poster_path"])
    release = data.get("release_date") or ""
    year = release[:4] if len(release) >= 4 and release[:4].isdigit() else movie["year"]
    db.execute(
        """UPDATE movies
           SET title=?,year=?,poster_path=?,tmdb_id=?,media_type=?,format=?,version=?,language=?,region=?,disc_count=?,review_pending=0,updated_at=CURRENT_TIMESTAMP
           WHERE id=? AND library_id=?""",
        (
            canonical_title, year, poster or movie["poster_path"], tmdb_id, media_type,
            values["format"], values["version"], values["language"], values["region"], values["disc_count"],
            movie["id"], movie["library_id"],
        ),
    )
    return metadata_changed, inferred

def _int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_movie(library_id: int, movie_id: int):
    movie = get_db().execute(
        "SELECT * FROM movies WHERE id=? AND library_id=?", (movie_id, library_id)
    ).fetchone()
    if not movie:
        abort(404)
    return movie


def _sync_collections(db, library_id: int, movie_id: int, form) -> None:
    selected_ids = []
    for raw in form.getlist("collection_ids"):
        try:
            selected_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    new_names = [x.strip() for x in (form.get("new_collections") or "").split(",") if x.strip()]
    for name in new_names:
        existing = db.execute(
            "SELECT id FROM collections WHERE library_id=? AND name=? COLLATE NOCASE",
            (library_id, name),
        ).fetchone()
        if existing:
            selected_ids.append(existing["id"])
        else:
            cur = db.execute("INSERT INTO collections (library_id,name) VALUES (?,?)", (library_id, name))
            selected_ids.append(cur.lastrowid)

    valid_ids = []
    for cid in set(selected_ids):
        row = db.execute("SELECT id FROM collections WHERE id=? AND library_id=?", (cid, library_id)).fetchone()
        if row:
            valid_ids.append(cid)

    db.execute("DELETE FROM movie_collections WHERE movie_id=?", (movie_id,))
    db.executemany(
        "INSERT INTO movie_collections (movie_id,collection_id) VALUES (?,?)",
        [(movie_id, cid) for cid in valid_ids],
    )


def _movie_form_values(form):
    return {
        "barcode": (form.get("barcode") or "").strip() or None,
        "title": (form.get("title") or "").strip(),
        "year": (form.get("year") or "").strip() or None,
        "format": (form.get("format") or "Blu-ray").strip(),
        "poster_path": (form.get("poster_path") or "").strip() or None,
        "tmdb_id": _int_or_none(form.get("tmdb_id")),
        "media_type": _media_type(form.get("media_type")),
        "status": (form.get("status") or "owned").strip(),
        "version": (form.get("version") or "").strip() or None,
        "country": (form.get("country") or "").strip() or None,
        "language": (form.get("language") or "").strip() or None,
        "region": (form.get("region") or "").strip() or None,
        "disc_count": _int_or_none(form.get("disc_count")),
        "notes": (form.get("notes") or "").strip() or None,
        "shelf_id": _int_or_none(form.get("shelf_id")),
    }


@bp.get("/libraries/<int:library_id>")
@login_required
@require_library_role("viewer")
def library_home(library_id, library, role):
    db = get_db()
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    fmt = (request.args.get("format") or "").strip()
    shelf_raw = (request.args.get("shelf") or "").strip()
    shelf = int(shelf_raw) if shelf_raw.isdigit() else None
    collection = request.args.get("collection", type=int)
    availability = (request.args.get("availability") or "").strip()
    sort = (request.args.get("sort") or "title").strip()
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(max(12, int(current_app.config.get("PAGE_SIZE", 60))), 200)

    where = ["m.library_id=?"]
    params = [library_id]
    if q:
        needle = f"%{q}%"
        where.append("(m.title LIKE ? OR m.year LIKE ? OR m.barcode LIKE ? OR m.notes LIKE ?)")
        params.extend([needle, needle, needle, needle])
    if status:
        where.append("m.status=?"); params.append(status)
    if fmt:
        where.append("m.format=?"); params.append(fmt)
    if shelf_raw == "unassigned":
        where.append("m.shelf_id IS NULL")
    elif shelf:
        where.append("m.shelf_id=?"); params.append(shelf)
    if collection:
        where.append("EXISTS (SELECT 1 FROM movie_collections mc WHERE mc.movie_id=m.id AND mc.collection_id=?)")
        params.append(collection)
    if availability == "loaned":
        where.append("l.id IS NOT NULL")
    elif availability == "available":
        where.append("l.id IS NULL")

    order_sql = {
        "title": "m.title COLLATE NOCASE ASC",
        "year": "COALESCE(m.year,'') DESC, m.title COLLATE NOCASE ASC",
        "recent": "m.id DESC",
        "shelf": "COALESCE(s.sort_order,999999), COALESCE(s.name,''), m.title COLLATE NOCASE",
    }.get(sort, "m.title COLLATE NOCASE ASC")

    join_sql = (
        "FROM movies m "
        "LEFT JOIN shelves s ON s.id=m.shelf_id "
        "LEFT JOIN loans l ON l.movie_id=m.id AND l.returned_date IS NULL "
    )
    where_sql = " WHERE " + " AND ".join(where)
    physical_rows = db.execute(
        "SELECT m.*, s.name AS shelf_name, l.id AS active_loan_id, l.borrower_name, l.loaned_date "
        + join_sql + where_sql + f" ORDER BY {order_sql}",
        params,
    ).fetchall()
    grouped_movies = _group_movie_rows(physical_rows)
    total = len(grouped_movies)
    offset = (page - 1) * page_size
    movies = grouped_movies[offset:offset + page_size]
    shelves = db.execute("SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE", (library_id,)).fetchall()
    collections = db.execute(
        "SELECT c.*, COUNT(mc.movie_id) AS movie_count FROM collections c "
        "LEFT JOIN movie_collections mc ON mc.collection_id=c.id WHERE c.library_id=? "
        "GROUP BY c.id ORDER BY c.name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    formats = [r[0] for r in db.execute("SELECT DISTINCT format FROM movies WHERE library_id=? AND format IS NOT NULL AND format<>'' ORDER BY format", (library_id,)).fetchall()]
    active_loans = db.execute("SELECT COUNT(*) FROM loans WHERE library_id=? AND returned_date IS NULL", (library_id,)).fetchone()[0]
    pending_review_count = db.execute(
        "SELECT COUNT(*) FROM movies WHERE library_id=? AND review_pending=1", (library_id,)
    ).fetchone()[0]
    pages = max(1, (total + page_size - 1) // page_size)
    return render_template(
        "catalogue.html", library=library, role=role, movies=movies, shelves=shelves,
        collections=collections, formats=formats, active_loans=active_loans,
        pending_review_count=pending_review_count, total=total, page=page, pages=pages,
    )


@bp.route("/libraries/<int:library_id>/movies/new", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def movie_new(library_id, library, role):
    db = get_db()

    # Adding starts with a TMDb search. Direct POST remains supported so CSV/tests
    # and old clients that submit the movie form are not broken.
    if request.method == "GET":
        query = (request.args.get("q") or "").strip()
        media_type = _media_type(request.args.get("media_type"))
        api_configured = bool(current_app.config.get("TMDB_API_KEY"))
        results = []
        if query and api_configured:
            try:
                results = _tmdb_search(query, media_type=media_type)
            except requests.RequestException:
                flash("TMDb search failed. Try again later or add the movie manually.", "error")
        return render_template(
            "movie_lookup.html",
            library=library,
            role=role,
            query=query,
            media_type=media_type,
            results=results,
            api_configured=api_configured,
            poster_size=current_app.config.get("TMDB_POSTER_SIZE", "w342"),
        )

    values = _movie_form_values(request.form)
    if not values["title"]:
        flash("Title is required.", "error")
    else:
        if values["shelf_id"]:
            shelf = db.execute(
                "SELECT id FROM shelves WHERE id=? AND library_id=?",
                (values["shelf_id"], library_id),
            ).fetchone()
            if not shelf:
                values["shelf_id"] = None
        cur = db.execute(
            """
            INSERT INTO movies (
                library_id,barcode,title,year,format,poster_path,tmdb_id,media_type,status,
                version,country,language,region,disc_count,notes,shelf_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (library_id, *[values[k] for k in MOVIE_FIELDS]),
        )
        _sync_collections(db, library_id, cur.lastrowid, request.form)
        db.commit()
        flash("Title added.", "success")
        return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=cur.lastrowid))

    shelves = db.execute(
        "SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    collections = db.execute(
        "SELECT * FROM collections WHERE library_id=? ORDER BY name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    return render_template(
        "movie_form.html",
        library=library,
        role=role,
        movie=None,
        prefill=request.form,
        shelves=shelves,
        collections=collections,
        selected_collections=[],
    )


@bp.get("/libraries/<int:library_id>/movies/new/manual")
@login_required
@require_library_role("editor")
def movie_new_manual(library_id, library, role):
    db = get_db()
    media_type = _media_type(request.args.get("media_type"))
    prefill = {"media_type": media_type}
    tmdb_id = request.args.get("tmdb_id", type=int)

    if tmdb_id:
        if not current_app.config.get("TMDB_API_KEY"):
            flash("TMDb lookup is unavailable because TMDB_API_KEY is not configured.", "warning")
        else:
            try:
                data = _tmdb_details(tmdb_id, media_type=media_type)
            except requests.RequestException:
                data = None
                flash("TMDb lookup failed. You can still add the movie manually.", "error")
            if data:
                countries = data.get("production_countries") or []
                prefill = {
                    "title": data.get("title") or "",
                    "year": (data.get("release_date") or "")[:4],
                    "media_type": media_type,
                    "format": "Blu-ray",
                    "status": "owned",
                    "poster_path": _tmdb_poster_url(data.get("poster_path")),
                    "tmdb_id": tmdb_id,
                    "language": data.get("original_language") or "",
                    "country": countries[0].get("name", "") if countries else "",
                }

    shelves = db.execute(
        "SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    collections = db.execute(
        "SELECT * FROM collections WHERE library_id=? ORDER BY name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    return render_template(
        "movie_form.html",
        library=library,
        role=role,
        movie=None,
        prefill=prefill,
        shelves=shelves,
        collections=collections,
        selected_collections=[],
    )


@bp.get("/libraries/<int:library_id>/movies/<int:movie_id>")
@login_required
@require_library_role("viewer")
def movie_detail(library_id, movie_id, library, role):
    db = get_db(); movie = _get_movie(library_id, movie_id)
    shelf = db.execute("SELECT * FROM shelves WHERE id=?", (movie["shelf_id"],)).fetchone() if movie["shelf_id"] else None
    collections = db.execute(
        "SELECT c.* FROM collections c JOIN movie_collections mc ON mc.collection_id=c.id WHERE mc.movie_id=? ORDER BY c.name COLLATE NOCASE",
        (movie_id,),
    ).fetchall()
    loans = db.execute("SELECT * FROM loans WHERE movie_id=? ORDER BY loaned_date DESC,id DESC", (movie_id,)).fetchall()
    active_loan = next((x for x in loans if not x["returned_date"]), None)
    copies = [movie]
    if movie["tmdb_id"]:
        copies = db.execute(
            "SELECT * FROM movies WHERE library_id=? AND media_type=? AND tmdb_id=? ORDER BY id",
            (library_id, _media_type(movie["media_type"]), movie["tmdb_id"]),
        ).fetchall()
    display_poster = movie["poster_path"] or next((copy["poster_path"] for copy in copies if copy["poster_path"]), None)
    return render_template("movie_detail.html", library=library, role=role, movie=movie, shelf=shelf, collections=collections, loans=loans, active_loan=active_loan, copies=copies, display_poster=display_poster)


@bp.route("/libraries/<int:library_id>/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def movie_edit(library_id, movie_id, library, role):
    db = get_db(); movie = _get_movie(library_id, movie_id)
    if request.method == "POST":
        values = _movie_form_values(request.form)
        if not values["title"]:
            flash("Title is required.", "error")
        else:
            if values["shelf_id"]:
                shelf = db.execute("SELECT id FROM shelves WHERE id=? AND library_id=?", (values["shelf_id"], library_id)).fetchone()
                if not shelf:
                    values["shelf_id"] = None
            db.execute(
                """
                UPDATE movies SET barcode=?,title=?,year=?,format=?,poster_path=?,tmdb_id=?,media_type=?,status=?,
                    version=?,country=?,language=?,region=?,disc_count=?,notes=?,shelf_id=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND library_id=?
                """,
                (*[values[k] for k in MOVIE_FIELDS], movie_id, library_id),
            )
            _sync_collections(db, library_id, movie_id, request.form)
            db.commit(); flash("Movie updated.", "success")
            return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
    shelves = db.execute("SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE", (library_id,)).fetchall()
    collections = db.execute("SELECT * FROM collections WHERE library_id=? ORDER BY name COLLATE NOCASE", (library_id,)).fetchall()
    selected = [r[0] for r in db.execute("SELECT collection_id FROM movie_collections WHERE movie_id=?", (movie_id,)).fetchall()]
    return render_template("movie_form.html", library=library, role=role, movie=movie, shelves=shelves, collections=collections, selected_collections=selected)


@bp.post("/libraries/<int:library_id>/movies/<int:movie_id>/delete")
@login_required
@require_library_role("editor")
def movie_delete(library_id, movie_id, library, role):
    movie = _get_movie(library_id, movie_id)
    if request.form.get("confirmation") != movie["title"]:
        flash("Type the movie title exactly to delete it.", "error")
        return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
    db = get_db(); db.execute("DELETE FROM movies WHERE id=? AND library_id=?", (movie_id, library_id)); db.commit()
    flash("Movie deleted.", "success")
    return redirect(url_for("catalog.library_home", library_id=library_id))


@bp.get("/libraries/<int:library_id>/loans")
@login_required
@require_library_role("viewer")
def loans(library_id, library, role):
    q = (request.args.get("q") or "").strip()
    db = get_db(); params = [library_id]; extra = ""
    if q:
        extra = " AND (m.title LIKE ? OR l.borrower_name LIKE ? OR l.phone LIKE ?)"
        needle = f"%{q}%"; params.extend([needle, needle, needle])
    rows = db.execute(
        """
        SELECT l.*, m.title, m.poster_path
        FROM loans l JOIN movies m ON m.id=l.movie_id
        WHERE l.library_id=? AND l.returned_date IS NULL
        """ + extra + " ORDER BY l.loaned_date ASC,l.id ASC",
        params,
    ).fetchall()
    return render_template("loans.html", library=library, role=role, loans=rows, q=q)


@bp.post("/libraries/<int:library_id>/movies/<int:movie_id>/loan")
@login_required
@require_library_role("editor")
def loan_movie(library_id, movie_id, library, role):
    movie = _get_movie(library_id, movie_id)
    borrower = (request.form.get("borrower_name") or "").strip()
    phone = (request.form.get("phone") or "").strip() or None
    loaned_date = (request.form.get("loaned_date") or "").strip() or date.today().isoformat()
    notes = (request.form.get("notes") or "").strip() or None
    if not borrower:
        flash("Borrower name is required.", "error")
    else:
        db = get_db()
        existing = db.execute("SELECT id FROM loans WHERE movie_id=? AND returned_date IS NULL", (movie_id,)).fetchone()
        if existing:
            flash("That movie is already on loan.", "warning")
        else:
            db.execute(
                "INSERT INTO loans (library_id,movie_id,borrower_name,phone,loaned_date,notes) VALUES (?,?,?,?,?,?)",
                (library_id, movie_id, borrower, phone, loaned_date, notes),
            )
            db.commit(); flash(f"{movie['title']} loaned to {borrower}.", "success")
    return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))


@bp.post("/libraries/<int:library_id>/movies/<int:movie_id>/return")
@login_required
@require_library_role("editor")
def return_movie(library_id, movie_id, library, role):
    _get_movie(library_id, movie_id)
    db = get_db()
    db.execute("UPDATE loans SET returned_date=? WHERE movie_id=? AND returned_date IS NULL", (date.today().isoformat(), movie_id))
    db.commit(); flash("Movie marked returned.", "success")
    return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))


@bp.route("/libraries/<int:library_id>/shelves", methods=["GET", "POST"])
@login_required
@require_library_role("viewer")
def shelves(library_id, library, role):
    db = get_db()
    if request.method == "POST":
        if role == "viewer": abort(403)
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        if not name:
            flash("Shelf name is required.", "error")
        else:
            try:
                db.execute("INSERT INTO shelves (library_id,name,description) VALUES (?,?,?)", (library_id, name, description)); db.commit()
                flash("Shelf added.", "success")
            except Exception:
                db.rollback(); flash("A shelf with that name already exists.", "warning")
        return redirect(url_for("catalog.shelves", library_id=library_id))
    rows = db.execute(
        "SELECT s.*,COUNT(m.id) AS movie_count FROM shelves s LEFT JOIN movies m ON m.shelf_id=s.id "
        "WHERE s.library_id=? GROUP BY s.id ORDER BY s.sort_order,s.name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    unassigned = db.execute("SELECT COUNT(*) FROM movies WHERE library_id=? AND shelf_id IS NULL", (library_id,)).fetchone()[0]
    return render_template("shelves.html", library=library, role=role, shelves=rows, unassigned=unassigned)


@bp.post("/libraries/<int:library_id>/shelves/<int:shelf_id>/edit")
@login_required
@require_library_role("editor")
def shelf_edit(library_id, shelf_id, library, role):
    db = get_db()
    shelf = db.execute("SELECT id FROM shelves WHERE id=? AND library_id=?", (shelf_id, library_id)).fetchone()
    if not shelf: abort(404)
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    sort_order = _int_or_none(request.form.get("sort_order")) or 0
    if name:
        try:
            db.execute("UPDATE shelves SET name=?,description=?,sort_order=? WHERE id=?", (name, description, sort_order, shelf_id)); db.commit()
            flash("Shelf updated.", "success")
        except Exception:
            db.rollback(); flash("Shelf name must be unique in this Library.", "error")
    return redirect(url_for("catalog.shelves", library_id=library_id))


@bp.post("/libraries/<int:library_id>/shelves/<int:shelf_id>/delete")
@login_required
@require_library_role("editor")
def shelf_delete(library_id, shelf_id, library, role):
    db = get_db(); db.execute("DELETE FROM shelves WHERE id=? AND library_id=?", (shelf_id, library_id)); db.commit()
    flash("Shelf removed. Movies on it are now Unassigned.", "success")
    return redirect(url_for("catalog.shelves", library_id=library_id))


@bp.route("/libraries/<int:library_id>/collections", methods=["GET", "POST"])
@login_required
@require_library_role("viewer")
def collections(library_id, library, role):
    db = get_db()
    if request.method == "POST":
        if role == "viewer": abort(403)
        name = (request.form.get("name") or "").strip()
        if name:
            try:
                db.execute("INSERT INTO collections (library_id,name) VALUES (?,?)", (library_id, name)); db.commit()
                flash("Collection added.", "success")
            except Exception:
                db.rollback(); flash("That Collection already exists.", "warning")
        return redirect(url_for("catalog.collections", library_id=library_id))
    rows = db.execute(
        "SELECT c.*,COUNT(mc.movie_id) AS movie_count FROM collections c LEFT JOIN movie_collections mc ON mc.collection_id=c.id "
        "WHERE c.library_id=? GROUP BY c.id ORDER BY c.name COLLATE NOCASE",
        (library_id,),
    ).fetchall()
    return render_template("collections.html", library=library, role=role, collections=rows)


@bp.post("/libraries/<int:library_id>/collections/<int:collection_id>/delete")
@login_required
@require_library_role("editor")
def collection_delete(library_id, collection_id, library, role):
    db = get_db(); db.execute("DELETE FROM collections WHERE id=? AND library_id=?", (collection_id, library_id)); db.commit()
    flash("Collection removed. Movies were not deleted.", "success")
    return redirect(url_for("catalog.collections", library_id=library_id))


@bp.get("/libraries/<int:library_id>/export.csv")
@login_required
@require_library_role("viewer")
def export_csv(library_id, library, role):
    db = get_db(); output = io.StringIO(); writer = csv.writer(output)
    headers = ["barcode","title","year","format","poster_path","tmdb_id","media_type","status","version","country","language","region","disc_count","notes","shelf","collections"]
    writer.writerow(headers)
    rows = db.execute(
        "SELECT m.*,s.name AS shelf_name FROM movies m LEFT JOIN shelves s ON s.id=m.shelf_id WHERE m.library_id=? ORDER BY m.id",
        (library_id,),
    ).fetchall()
    for m in rows:
        names = [r[0] for r in db.execute(
            "SELECT c.name FROM collections c JOIN movie_collections mc ON mc.collection_id=c.id WHERE mc.movie_id=? ORDER BY c.name COLLATE NOCASE",
            (m["id"],),
        ).fetchall()]
        writer.writerow([m[h] for h in headers[:-2]] + [m["shelf_name"] or "", ";".join(names)])
    filename = f"{library['name'].replace(' ','_')}_movies.csv"
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.post("/libraries/<int:library_id>/import.csv")
@login_required
@require_library_role("editor")
def import_csv(library_id, library, role):
    upload = request.files.get("csv_file")
    if not upload or not upload.filename.lower().endswith(".csv"):
        flash("Choose a CSV file.", "error")
        return redirect(url_for("catalog.library_home", library_id=library_id))
    try:
        text = upload.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("CSV must be UTF-8 text.", "error")
        return redirect(url_for("catalog.library_home", library_id=library_id))
    db = get_db(); count = 0
    for row in csv.DictReader(io.StringIO(text)):
        title = (row.get("title") or "").strip()
        if not title: continue
        shelf_id = None
        shelf_name = (row.get("shelf") or "").strip()
        if shelf_name:
            shelf = db.execute("SELECT id FROM shelves WHERE library_id=? AND name=? COLLATE NOCASE", (library_id, shelf_name)).fetchone()
            if not shelf:
                cur = db.execute("INSERT INTO shelves (library_id,name) VALUES (?,?)", (library_id, shelf_name)); shelf_id = cur.lastrowid
            else: shelf_id = shelf["id"]
        cur = db.execute(
            """INSERT INTO movies (library_id,barcode,title,year,format,poster_path,tmdb_id,media_type,status,version,country,language,region,disc_count,notes,shelf_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (library_id, row.get("barcode") or None, title, row.get("year") or None, row.get("format") or "Blu-ray",
             row.get("poster_path") or None, _int_or_none(row.get("tmdb_id")), _media_type(row.get("media_type")), row.get("status") or "owned",
             row.get("version") or None, row.get("country") or None, row.get("language") or None,
             row.get("region") or None, _int_or_none(row.get("disc_count")), row.get("notes") or None, shelf_id),
        )
        movie_id = cur.lastrowid
        for name in [x.strip() for x in (row.get("collections") or "").split(";") if x.strip()]:
            coll = db.execute("SELECT id FROM collections WHERE library_id=? AND name=? COLLATE NOCASE", (library_id, name)).fetchone()
            if not coll:
                ccur = db.execute("INSERT INTO collections (library_id,name) VALUES (?,?)", (library_id, name)); cid = ccur.lastrowid
            else: cid = coll["id"]
            db.execute("INSERT OR IGNORE INTO movie_collections (movie_id,collection_id) VALUES (?,?)", (movie_id, cid))
        count += 1
    db.commit(); flash(f"Imported {count} movies.", "success")
    return redirect(url_for("catalog.library_home", library_id=library_id))



@bp.get("/libraries/<int:library_id>/match-repair")
@login_required
@require_library_role("editor")
def match_repair_page(library_id, library, role):
    if not current_app.config.get("TMDB_API_KEY"):
        flash("TMDB_API_KEY is not configured.", "warning")
        return redirect(url_for("catalog.library_home", library_id=library_id))
    db = get_db()
    unresolved_total = db.execute(
        "SELECT COUNT(*) AS n FROM movies WHERE library_id=? AND (tmdb_id IS NULL OR review_pending=1)",
        (library_id,),
    ).fetchone()["n"]
    library_total = db.execute(
        "SELECT COUNT(*) AS n FROM movies WHERE library_id=?", (library_id,)
    ).fetchone()["n"]
    return render_template(
        "match_repair.html", library=library, role=role,
        total=unresolved_total, unresolved_total=unresolved_total, library_total=library_total,
    )


@bp.post("/libraries/<int:library_id>/match-repair/batch")
@login_required
@require_library_role("editor")
def match_repair_batch(library_id, library, role):
    if not current_app.config.get("TMDB_API_KEY"):
        return jsonify({"error": "TMDB_API_KEY is not configured."}), 400
    payload = request.get_json(silent=True) or {}
    try:
        after_id = max(0, int(payload.get("after_id") or 0))
    except (TypeError, ValueError):
        after_id = 0
    refresh_matched = bool(payload.get("refresh_matched", False))

    db = get_db()
    if refresh_matched:
        rows = db.execute(
            "SELECT * FROM movies WHERE library_id=? AND id>? ORDER BY id LIMIT ?",
            (library_id, after_id, BULK_REPAIR_BATCH_SIZE),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM movies WHERE library_id=? AND id>? AND (tmdb_id IS NULL OR review_pending=1) ORDER BY id LIMIT ?",
            (library_id, after_id, BULK_REPAIR_BATCH_SIZE),
        ).fetchall()
    counts = {"processed": 0, "matched": 0, "refreshed": 0, "metadata": 0, "unmatched": 0, "failed": 0}
    details_cache = {}
    search_cache = {}

    for movie in rows:
        counts["processed"] += 1
        try:
            tmdb_id = movie["tmdb_id"]
            media_type = _media_type(movie["media_type"] if "media_type" in movie.keys() else "movie")
            data = None
            if tmdb_id:
                details_key = (media_type, tmdb_id)
                if details_key not in details_cache:
                    details_cache[details_key] = _tmdb_details(tmdb_id, media_type=media_type)
                data = details_cache[details_key]
                if data:
                    counts["refreshed"] += 1
            else:
                query_titles, query_year = _match_queries_for_movie(movie)
                choice = _find_high_confidence_match(query_titles, query_year, search_cache, media_type=media_type)
                if not choice:
                    db.execute(
                        "UPDATE movies SET review_pending=1, updated_at=CURRENT_TIMESTAMP WHERE id=? AND library_id=?",
                        (movie["id"], library_id),
                    )
                    counts["unmatched"] += 1
                    continue
                tmdb_id = choice["tmdb_id"]
                details_key = (media_type, tmdb_id)
                if details_key not in details_cache:
                    details_cache[details_key] = _tmdb_details(tmdb_id, media_type=media_type)
                data = details_cache[details_key]
                if data:
                    counts["matched"] += 1
            if not data:
                counts["failed"] += 1
                continue
            metadata_changed, _ = _apply_identified_movie(db, movie, data, tmdb_id, media_type=media_type)
            if metadata_changed:
                counts["metadata"] += 1
        except requests.RequestException:
            counts["failed"] += 1

    db.commit()
    next_after_id = rows[-1]["id"] if rows else after_id
    if refresh_matched:
        more = db.execute(
            "SELECT 1 FROM movies WHERE library_id=? AND id>? LIMIT 1", (library_id, next_after_id)
        ).fetchone() is not None
    else:
        more = db.execute(
            "SELECT 1 FROM movies WHERE library_id=? AND id>? AND (tmdb_id IS NULL OR review_pending=1) LIMIT 1",
            (library_id, next_after_id),
        ).fetchone() is not None
    return jsonify({**counts, "after_id": next_after_id, "done": not more})


@bp.route("/libraries/<int:library_id>/match-repair/review", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def match_repair_review(library_id, library, role):
    if not current_app.config.get("TMDB_API_KEY"):
        flash("TMDB_API_KEY is not configured.", "warning")
        return redirect(url_for("catalog.library_home", library_id=library_id))

    db = get_db()
    if request.method == "POST":
        movie_id = _int_or_none(request.form.get("movie_id"))
        if not movie_id:
            abort(400)
        movie = _get_movie(library_id, movie_id)
        action = (request.form.get("action") or "match").strip().lower()
        if action == "dismiss":
            db.execute(
                "UPDATE movies SET review_pending=0, updated_at=CURRENT_TIMESTAMP WHERE id=? AND library_id=?",
                (movie_id, library_id),
            )
            db.commit()
            flash(f"Removed {movie['title']} from the review list.", "success")
            return redirect(url_for("catalog.match_repair_review", library_id=library_id, after_id=movie_id))

        tmdb_id = _int_or_none(request.form.get("tmdb_id"))
        media_type = _media_type(request.form.get("media_type") or (movie["media_type"] if "media_type" in movie.keys() else "movie"))
        if not tmdb_id:
            abort(400)
        try:
            data = _tmdb_details(tmdb_id, media_type=media_type)
        except requests.RequestException:
            flash("TMDb lookup failed. Try again later.", "error")
            return redirect(url_for("catalog.match_repair_review", library_id=library_id, after_id=movie_id))
        if not data:
            flash("TMDb lookup failed. Try again later.", "error")
            return redirect(url_for("catalog.match_repair_review", library_id=library_id, after_id=movie_id))
        metadata_changed, _ = _apply_identified_movie(db, movie, data, tmdb_id, media_type=media_type)
        db.commit()
        message = f"Matched {movie['title']} with TMDb."
        if metadata_changed:
            message += " Copy metadata was recovered too."
        flash(message, "success")
        return redirect(url_for("catalog.match_repair_review", library_id=library_id, after_id=movie_id))

    try:
        after_id = max(0, int(request.args.get("after_id") or 0))
    except (TypeError, ValueError):
        after_id = 0

    remaining_review = db.execute(
        "SELECT COUNT(*) AS n FROM movies WHERE library_id=? AND review_pending=1",
        (library_id,),
    ).fetchone()["n"]
    movie = db.execute(
        "SELECT * FROM movies WHERE library_id=? AND review_pending=1 AND id>? ORDER BY id LIMIT 1",
        (library_id, after_id),
    ).fetchone()

    if not movie:
        return render_template(
            "match_repair_review.html",
            library=library, role=role, movie=None, results=[], poster_size=current_app.config.get("TMDB_POSTER_SIZE", "w342"),
            remaining_review=remaining_review, after_id=after_id, search_title="",
        )

    search_title = (request.args.get("search_title") or "").strip()
    media_type = _media_type(request.args.get("media_type") or (movie["media_type"] if "media_type" in movie.keys() else "movie"))
    if search_title:
        query_titles = search_ready_title_candidates(search_title, media_type=media_type)
        if search_title not in query_titles:
            query_titles.insert(0, search_title)
        query_year = None
    else:
        query_titles, query_year = _match_queries_for_movie(movie)
    try:
        results = _tmdb_search_candidates(query_titles, query_year, max_searches=MAX_MATCH_SEARCHES, media_type=media_type)
    except requests.RequestException:
        results = []
        flash("TMDb search failed for this movie. You can skip it and continue.", "error")
    for result in results:
        result["metadata_preview"] = infer_copy_metadata_from_legacy_title(
            movie["title"], result.get("title") or movie["title"], media_type=media_type
        )
    return render_template(
        "match_repair_review.html",
        library=library, role=role, movie=movie, results=results, poster_size=current_app.config.get("TMDB_POSTER_SIZE", "w342"),
        remaining_review=remaining_review, after_id=after_id, search_title=search_title, media_type=media_type,
    )


def _normalize_tmdb_payload(item, media_type="movie"):
    media_type = _media_type(media_type)
    if media_type == "tv":
        title = item.get("name") or item.get("original_name") or ""
        date = item.get("first_air_date") or ""
    else:
        title = item.get("title") or item.get("original_title") or ""
        date = item.get("release_date") or ""
    normalized = dict(item)
    normalized["title"] = title
    normalized["release_date"] = date
    normalized["media_type"] = media_type
    return normalized


def _tmdb_search(title: str, year: str | None = None, media_type="movie"):
    api_key = current_app.config.get("TMDB_API_KEY") or ""
    if not api_key:
        return []
    media_type = _media_type(media_type)
    params = {"api_key": api_key, "query": title}
    if year:
        params["first_air_date_year" if media_type == "tv" else "year"] = year
    response = requests.get(f"https://api.themoviedb.org/3/search/{media_type}", params=params, timeout=10)
    response.raise_for_status()
    return [_normalize_tmdb_payload(item, media_type) for item in response.json().get("results", [])[:20]]


def _tmdb_details(tmdb_id: int, media_type="movie"):
    api_key = current_app.config.get("TMDB_API_KEY") or ""
    if not api_key:
        return None
    media_type = _media_type(media_type)
    response = requests.get(
        f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}",
        params={"api_key": api_key},
        timeout=10,
    )
    response.raise_for_status()
    return _normalize_tmdb_payload(response.json(), media_type)


def _tmdb_poster_url(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    if poster_path.startswith("http://") or poster_path.startswith("https://"):
        return poster_path
    size = current_app.config.get("TMDB_POSTER_SIZE", "w342")
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"


@bp.route("/libraries/<int:library_id>/movies/<int:movie_id>/identify", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def identify_movie(library_id, movie_id, library, role):
    db = get_db(); movie = _get_movie(library_id, movie_id)
    api_key = current_app.config.get("TMDB_API_KEY") or ""
    if not api_key:
        flash("TMDB_API_KEY is not configured.", "warning")
        return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
    if request.method == "POST":
        tmdb_id = _int_or_none(request.form.get("tmdb_id"))
        media_type = _media_type(request.form.get("media_type") or (movie["media_type"] if "media_type" in movie.keys() else "movie"))
        if not tmdb_id: abort(400)
        try:
            data = _tmdb_details(tmdb_id, media_type=media_type)
        except requests.RequestException:
            flash("TMDb lookup failed. Try again later.", "error")
            return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
        if not data:
            flash("TMDb lookup failed. Try again later.", "error")
            return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
        metadata_changed, _ = _apply_identified_movie(db, movie, data, tmdb_id, media_type=media_type)
        db.commit()
        message = "Movie identified with TMDb."
        if metadata_changed:
            message += " Copy metadata was recovered from the old title."
        flash(message, "success")
        return redirect(url_for("catalog.movie_detail", library_id=library_id, movie_id=movie_id))
    media_type = _media_type(request.args.get("media_type") or (movie["media_type"] if "media_type" in movie.keys() else "movie"))
    query_titles, query_year = _match_queries_for_movie(movie)
    try:
        results = _tmdb_search_candidates(query_titles, query_year, media_type=media_type)
    except requests.RequestException:
        results = []; flash("TMDb search failed. Try again later.", "error")
    for result in results:
        result["metadata_preview"] = infer_copy_metadata_from_legacy_title(
            movie["title"], result.get("title") or movie["title"], media_type=media_type
        )
    poster_size = current_app.config.get("TMDB_POSTER_SIZE", "w342")
    return render_template("identify.html", library=library, role=role, movie=movie, results=results, poster_size=poster_size, media_type=media_type)
