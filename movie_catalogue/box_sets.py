from __future__ import annotations

import csv
import io
from datetime import date

import requests
from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from .db import get_db
from .permissions import require_library_role
from .integrations import tmdb_collection_search, tmdb_collection_details, tmdb_search
from .barcode_parser import parse_barcode_product_title
from .box_set_service import (
    BoxSetLoanConflict,
    box_set_effective_state,
    box_set_has_loan_history,
    create_box_set,
    get_box_set,
    get_box_set_members,
    loan_box_set,
    loan_box_set_member,
    member_effective_state,
    return_box_set,
    return_box_set_member,
)

bp = Blueprint("box_sets", __name__)


def _poster_url(path):
    if not path:
        return None
    value = str(path)
    if value.startswith("http://") or value.startswith("https://"):
        return value
    size = current_app.config.get("TMDB_POSTER_SIZE", "w342")
    return f"https://image.tmdb.org/t/p/{size}{value if value.startswith('/') else '/' + value}"


def _int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _physical_from_form(form, defaults=None):
    defaults = defaults or {}
    title = (form.get("title") or defaults.get("title") or "").strip()
    return {
        "barcode": (form.get("barcode") or defaults.get("barcode") or "").strip() or None,
        "title": title,
        "tmdb_collection_id": _int(form.get("tmdb_collection_id") or defaults.get("tmdb_collection_id")),
        "poster_path": (form.get("poster_path") or defaults.get("poster_path") or "").strip() or None,
        "format": (form.get("format") or defaults.get("format") or "Blu-ray").strip() or None,
        "version": (form.get("version") or defaults.get("version") or "").strip() or None,
        "country": (form.get("country") or defaults.get("country") or "").strip() or None,
        "language": (form.get("language") or defaults.get("language") or "").strip() or None,
        "region": (form.get("region") or defaults.get("region") or "").strip() or None,
        "disc_count": _int(form.get("disc_count") or defaults.get("disc_count")),
        "notes": (form.get("notes") or defaults.get("notes") or "").strip() or None,
        "shelf_id": _int(form.get("shelf_id") or defaults.get("shelf_id")),
        "status": (form.get("status") or defaults.get("status") or "owned").strip() or "owned",
    }


def _validate_shelf(db, library_id, shelf_id):
    if not shelf_id:
        return None
    row = db.execute("SELECT id FROM shelves WHERE id=? AND library_id=?", (shelf_id, library_id)).fetchone()
    return shelf_id if row else None


def _collection_members(details, selected_ids=None):
    selected = None if selected_ids is None else {int(x) for x in selected_ids}
    members = []
    for part in details.get("parts") or []:
        if selected is not None and int(part.get("id") or 0) not in selected:
            continue
        release = part.get("release_date") or ""
        members.append({
            "tmdb_id": part.get("id"),
            "title": part.get("title") or "Untitled",
            "year": release[:4] if len(release) >= 4 else None,
            "poster_path": _poster_url(part.get("poster_path")),
            "position": int(part.get("position", len(members))),
        })
    return members


@bp.get("/libraries/<int:library_id>/box-sets/new")
@login_required
@require_library_role("editor")
def new_box_set(library_id, library, role):
    query = (request.args.get("q") or "").strip()
    results = []
    api_configured = bool(current_app.config.get("TMDB_API_KEY"))
    if query and api_configured:
        try:
            results = tmdb_collection_search(query)
        except requests.RequestException:
            flash("TMDb Collection search failed. Try again later.", "error")
    return render_template("box_set_lookup.html", library=library, role=role, query=query, results=results, api_configured=api_configured)


@bp.route("/libraries/<int:library_id>/box-sets/new/confirm", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def confirm_new_box_set(library_id, library, role):
    collection_id = request.args.get("tmdb_collection_id", type=int) or _int(request.form.get("tmdb_collection_id"))
    if not collection_id:
        abort(400)
    try:
        details = tmdb_collection_details(collection_id)
    except requests.RequestException:
        details = None
    if not details:
        flash("TMDb Collection details could not be loaded.", "error")
        return redirect(url_for("box_sets.new_box_set", library_id=library_id))
    db = get_db()
    shelves = db.execute("SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE", (library_id,)).fetchall()
    if request.method == "POST":
        selected = request.form.getlist("member_tmdb_id")
        valid = {str(part.get("id")) for part in details.get("parts") or []}
        selected = [x for x in selected if x in valid]
        physical = _physical_from_form(request.form, {
            "title": details.get("title"), "tmdb_collection_id": collection_id,
            "poster_path": _poster_url(details.get("poster_path")),
        })
        physical["shelf_id"] = _validate_shelf(db, library_id, physical["shelf_id"])
        if not physical["title"]:
            flash("Title is required.", "error")
        elif not selected:
            flash("Select at least one contained film.", "error")
        else:
            try:
                box_id = create_box_set(db, library_id, physical, _collection_members(details, selected))
                flash(f"Added {physical['title']} with {len(selected)} contained films.", "success")
                return redirect(url_for("box_sets.detail", library_id=library_id, box_set_id=box_id))
            except Exception as exc:
                current_app.logger.exception("Box-set creation failed")
                flash(f"Could not save the box set: {exc}", "error")
    raw_title = (request.args.get("raw_title") or "").strip()
    parsed = parse_barcode_product_title(raw_title) if raw_title else None
    prefill = {
        "title": raw_title or details.get("title") or "",
        "tmdb_collection_id": collection_id,
        "poster_path": _poster_url(details.get("poster_path")),
        "format": parsed.format if parsed else "Blu-ray",
        "version": parsed.edition if parsed else None,
        "language": parsed.language if parsed else None,
        "region": parsed.region if parsed else None,
        "disc_count": parsed.disc_count if parsed else None,
        "barcode": request.args.get("barcode") or "",
    }
    return render_template("box_set_confirm.html", library=library, role=role, details=details, shelves=shelves, prefill=prefill)


@bp.get("/libraries/<int:library_id>/box-sets/<int:box_set_id>")
@login_required
@require_library_role("viewer")
def detail(library_id, box_set_id, library, role):
    db = get_db()
    box = get_box_set(db, library_id, box_set_id)
    if not box:
        abort(404)
    members = []
    for row in get_box_set_members(db, box_set_id):
        item = dict(row)
        item["effective"] = member_effective_state(db, row["id"])
        members.append(item)
    return render_template("box_set_detail.html", library=library, role=role, box_set=box, members=members, state=box_set_effective_state(db, box_set_id))


@bp.route("/libraries/<int:library_id>/box-sets/<int:box_set_id>/edit", methods=["GET", "POST"])
@login_required
@require_library_role("editor")
def edit(library_id, box_set_id, library, role):
    db = get_db(); box = get_box_set(db, library_id, box_set_id)
    if not box: abort(404)
    shelves = db.execute("SELECT * FROM shelves WHERE library_id=? ORDER BY sort_order,name COLLATE NOCASE", (library_id,)).fetchall()
    if request.method == "POST":
        physical = _physical_from_form(request.form, dict(box))
        physical["shelf_id"] = _validate_shelf(db, library_id, physical["shelf_id"])
        if not physical["title"]:
            flash("Title is required.", "error")
        else:
            db.execute("""UPDATE box_sets SET barcode=?,title=?,tmdb_collection_id=?,poster_path=?,format=?,version=?,country=?,language=?,region=?,disc_count=?,notes=?,shelf_id=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND library_id=?""",
                       (*[physical[k] for k in ("barcode","title","tmdb_collection_id","poster_path","format","version","country","language","region","disc_count","notes","shelf_id","status")], box_set_id, library_id))
            db.commit(); flash("Box set updated.", "success")
            return redirect(url_for("box_sets.detail", library_id=library_id, box_set_id=box_set_id))
    return render_template("box_set_edit.html", library=library, role=role, box_set=box, shelves=shelves)


@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/members/add")
@login_required
@require_library_role("editor")
def add_member(library_id, box_set_id, library, role):
    db=get_db(); box=get_box_set(db,library_id,box_set_id)
    if not box: abort(404)
    query=(request.form.get("member_query") or "").strip()
    tmdb_id=_int(request.form.get("member_tmdb_id"))
    if tmdb_id:
        title=(request.form.get("member_title") or "").strip()
        year=(request.form.get("member_year") or "").strip() or None
        poster=(request.form.get("member_poster_path") or "").strip() or None
        if not title:
            flash("Contained film title is required.","error")
        else:
            pos=db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM box_set_members WHERE box_set_id=?",(box_set_id,)).fetchone()[0]
            try:
                db.execute("INSERT INTO box_set_members(box_set_id,tmdb_id,title,year,poster_path,position) VALUES (?,?,?,?,?,?)",(box_set_id,tmdb_id,title,year,_poster_url(poster),pos)); db.commit(); flash("Contained film added.","success")
            except Exception:
                db.rollback(); flash("That film is already in this box set.","warning")
    elif query:
        try:
            results=tmdb_search(query, media_type="movie")
        except Exception:
            results=[]; flash("TMDb movie search failed.","error")
        members=[]
        for row in get_box_set_members(db,box_set_id):
            item=dict(row); item["effective"]=member_effective_state(db,row["id"]); members.append(item)
        return render_template("box_set_detail.html",library=library,role=role,box_set=box,members=members,state=box_set_effective_state(db,box_set_id),member_search=query,member_results=results)
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))


@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/members/<int:member_id>/remove")
@login_required
@require_library_role("editor")
def remove_member(library_id, box_set_id, member_id, library, role):
    db=get_db(); box=get_box_set(db,library_id,box_set_id)
    if not box: abort(404)
    member=db.execute("SELECT * FROM box_set_members WHERE id=? AND box_set_id=?",(member_id,box_set_id)).fetchone()
    if not member: abort(404)
    if db.execute("SELECT 1 FROM box_set_member_loans WHERE box_set_member_id=? LIMIT 1",(member_id,)).fetchone():
        flash("This contained film has loan history and cannot be removed in this release.","warning")
    else:
        db.execute("DELETE FROM box_set_members WHERE id=?",(member_id,)); db.commit(); flash("Contained film removed.","success")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))


@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/members/reorder")
@login_required
@require_library_role("editor")
def reorder_members(library_id, box_set_id, library, role):
    db=get_db(); box=get_box_set(db,library_id,box_set_id)
    if not box: abort(404)
    valid={r[0] for r in db.execute("SELECT id FROM box_set_members WHERE box_set_id=?",(box_set_id,)).fetchall()}
    ranked=[]
    for mid in valid:
        raw=request.form.get(f"position_{mid}")
        try: position=int(raw)
        except (TypeError,ValueError): position=999999
        ranked.append((position,mid))
    ranked.sort(key=lambda item:(item[0],item[1]))
    for position,(_requested,mid) in enumerate(ranked): db.execute("UPDATE box_set_members SET position=? WHERE id=?",(position,mid))
    db.commit(); flash("Film order updated.","success")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))


@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/delete")
@login_required
@require_library_role("editor")
def delete(library_id, box_set_id, library, role):
    db=get_db(); box=get_box_set(db,library_id,box_set_id)
    if not box: abort(404)
    if request.form.get("confirmation") != box["title"]:
        flash("Type the box-set title exactly to delete it.","error")
    elif box_set_has_loan_history(db,box_set_id):
        flash("This box set has loan history and cannot be deleted in this release.","warning")
    else:
        db.execute("DELETE FROM box_sets WHERE id=? AND library_id=?",(box_set_id,library_id)); db.commit(); flash("Box set deleted.","success")
        return redirect(url_for("catalog.library_home",library_id=library_id))
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))


def _loan_form():
    return ((request.form.get("borrower_name") or "").strip(),(request.form.get("phone") or "").strip() or None,(request.form.get("loaned_date") or "").strip() or date.today().isoformat(),(request.form.get("notes") or "").strip() or None)

@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/loan")
@login_required
@require_library_role("editor")
def loan(library_id,box_set_id,library,role):
    db=get_db(); box=get_box_set(db,library_id,box_set_id)
    if not box: abort(404)
    try: loan_box_set(db,library_id,box_set_id,*_loan_form()); flash("Box set loaned.","success")
    except (BoxSetLoanConflict,ValueError) as exc: flash(str(exc),"warning")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))

@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/return")
@login_required
@require_library_role("editor")
def return_whole(library_id,box_set_id,library,role):
    db=get_db();
    if not get_box_set(db,library_id,box_set_id): abort(404)
    return_box_set(db,library_id,box_set_id); flash("Box set marked returned.","success")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id))

@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/members/<int:member_id>/loan")
@login_required
@require_library_role("editor")
def loan_member(library_id,box_set_id,member_id,library,role):
    db=get_db()
    try: loan_box_set_member(db,library_id,member_id,*_loan_form()); flash("Contained film loaned.","success")
    except (BoxSetLoanConflict,ValueError) as exc: flash(str(exc),"warning")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id)+f"#member-{member_id}")

@bp.post("/libraries/<int:library_id>/box-sets/<int:box_set_id>/members/<int:member_id>/return")
@login_required
@require_library_role("editor")
def return_member(library_id,box_set_id,member_id,library,role):
    return_box_set_member(get_db(),library_id,member_id); flash("Contained film marked returned.","success")
    return redirect(url_for("box_sets.detail",library_id=library_id,box_set_id=box_set_id)+f"#member-{member_id}")


CSV_HEADERS=["box_set_key","barcode","title","tmdb_collection_id","poster_path","format","version","country","language","region","disc_count","notes","shelf","member_tmdb_id","member_title","member_year","member_poster_path","member_position"]

@bp.get("/libraries/<int:library_id>/box-sets/export.csv")
@login_required
@require_library_role("viewer")
def export_csv(library_id,library,role):
    db=get_db(); output=io.StringIO(); w=csv.DictWriter(output,fieldnames=CSV_HEADERS); w.writeheader()
    rows=db.execute("""SELECT bs.*,s.name shelf_name,bsm.tmdb_id member_tmdb_id,bsm.title member_title,bsm.year member_year,bsm.poster_path member_poster_path,bsm.position member_position FROM box_sets bs LEFT JOIN shelves s ON s.id=bs.shelf_id LEFT JOIN box_set_members bsm ON bsm.box_set_id=bs.id WHERE bs.library_id=? ORDER BY bs.id,bsm.position,bsm.id""",(library_id,)).fetchall()
    for r in rows:
        d=dict(r); w.writerow({"box_set_key":str(r["id"]),"barcode":r["barcode"],"title":r["title"],"tmdb_collection_id":r["tmdb_collection_id"],"poster_path":r["poster_path"],"format":r["format"],"version":r["version"],"country":r["country"],"language":r["language"],"region":r["region"],"disc_count":r["disc_count"],"notes":r["notes"],"shelf":d.get("shelf_name"),"member_tmdb_id":d.get("member_tmdb_id"),"member_title":d.get("member_title"),"member_year":d.get("member_year"),"member_poster_path":d.get("member_poster_path"),"member_position":d.get("member_position")})
    return Response(output.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename=homebuster-box-sets-{library_id}.csv"})

@bp.post("/libraries/<int:library_id>/box-sets/import.csv")
@login_required
@require_library_role("editor")
def import_csv(library_id,library,role):
    file=request.files.get("csv_file")
    if not file: flash("Choose a box-set CSV file.","error"); return redirect(url_for("catalog.library_home",library_id=library_id))
    try: rows=list(csv.DictReader(io.StringIO(file.read().decode("utf-8-sig"))))
    except Exception: flash("Could not read that CSV.","error"); return redirect(url_for("catalog.library_home",library_id=library_id))
    if not rows or not set(CSV_HEADERS).issubset(rows[0].keys()): flash("That is not a Homebuster box-set CSV.","error"); return redirect(url_for("catalog.library_home",library_id=library_id))
    groups={}
    for row in rows: groups.setdefault(row.get("box_set_key") or f"row-{len(groups)}",[]).append(row)
    db=get_db(); created=0
    shelves={str(r["name"]).casefold():r["id"] for r in db.execute("SELECT id,name FROM shelves WHERE library_id=?",(library_id,)).fetchall()}
    for key,group in groups.items():
        first=group[0]
        members=[]
        try:
            for row in group:
                if not (row.get("member_title") or "").strip(): raise ValueError("member title missing")
                members.append({"tmdb_id":_int(row.get("member_tmdb_id")),"title":row.get("member_title"),"year":row.get("member_year") or None,"poster_path":row.get("member_poster_path") or None,"position":_int(row.get("member_position")) or 0})
            physical={k:(first.get(k) or None) for k in ("barcode","title","poster_path","format","version","country","language","region","notes")}
            physical.update({"tmdb_collection_id":_int(first.get("tmdb_collection_id")),"disc_count":_int(first.get("disc_count")),"shelf_id":shelves.get((first.get("shelf") or "").casefold()),"status":"owned"})
            create_box_set(db,library_id,physical,members); created+=1
        except Exception as exc:
            current_app.logger.warning("Skipping invalid box-set CSV group %s: %s",key,exc)
    flash(f"Imported {created} box sets.","success" if created else "warning")
    return redirect(url_for("catalog.library_home",library_id=library_id))
