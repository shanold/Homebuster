from __future__ import annotations

from datetime import date

from .smart_collections import ensure_organizational_collection_for_box_set


PHYSICAL_FIELDS = (
    "barcode", "title", "tmdb_collection_id", "poster_path", "format", "version",
    "country", "language", "region", "disc_count", "notes", "shelf_id", "status",
)


class BoxSetLoanConflict(ValueError):
    pass


def get_box_set(db, library_id: int, box_set_id: int):
    return db.execute(
        """SELECT bs.*, s.name AS shelf_name
           FROM box_sets bs LEFT JOIN shelves s ON s.id=bs.shelf_id
           WHERE bs.id=? AND bs.library_id=?""",
        (box_set_id, library_id),
    ).fetchone()


def get_box_set_members(db, box_set_id: int) -> list:
    return db.execute(
        """SELECT m.*, m.parent_box_set_position AS position
           FROM movies m
           WHERE m.parent_box_set_id=?
           ORDER BY COALESCE(m.parent_box_set_position,999999), COALESCE(m.year,''), m.id""",
        (box_set_id,),
    ).fetchall()


def _normalize_member(member: dict, position: int) -> dict:
    title = str(member.get("title") or "").strip()
    if not title:
        raise ValueError("Every box-set member needs a title")
    year = member.get("year")
    return {
        "tmdb_id": member.get("tmdb_id"),
        "title": title,
        "year": str(year) if year not in (None, "") else None,
        "poster_path": member.get("poster_path"),
        "position": int(member.get("position", position)),
    }


def reconcile_box_set_members(db, library_id: int, box_set_id: int, members: list[dict]) -> list[int]:
    """Create/update first-class contained movies without duplicating parent+TMDb identity."""
    member_ids = []
    seen_ids = set()
    for position, raw in enumerate(members):
        member = _normalize_member(raw, position)
        existing = None
        if member["tmdb_id"] is not None:
            existing = db.execute(
                """SELECT * FROM movies WHERE library_id=? AND parent_box_set_id=?
                   AND media_type='movie' AND tmdb_id=? ORDER BY id LIMIT 1""",
                (library_id, box_set_id, member["tmdb_id"]),
            ).fetchone()
        if existing is None:
            existing = db.execute(
                """SELECT * FROM movies WHERE library_id=? AND parent_box_set_id=?
                   AND title=? COLLATE NOCASE AND COALESCE(year,'')=COALESCE(?, '') ORDER BY id LIMIT 1""",
                (library_id, box_set_id, member["title"], member["year"]),
            ).fetchone()
        if existing:
            movie_id = int(existing["id"])
            db.execute(
                """UPDATE movies SET title=?,year=?,poster_path=COALESCE(?,poster_path),tmdb_id=COALESCE(?,tmdb_id),
                   media_type='movie',review_pending=0,parent_box_set_position=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND library_id=?""",
                (member["title"], member["year"], member["poster_path"], member["tmdb_id"], member["position"], movie_id, library_id),
            )
        else:
            cur = db.execute(
                """INSERT INTO movies(
                    library_id,title,year,poster_path,tmdb_id,media_type,status,review_pending,
                    parent_box_set_id,parent_box_set_position
                ) VALUES (?,?,?,?,?,'movie','owned',0,?,?)""",
                (library_id, member["title"], member["year"], member["poster_path"], member["tmdb_id"], box_set_id, member["position"]),
            )
            movie_id = int(cur.lastrowid)
        member_ids.append(movie_id)
        seen_ids.add(movie_id)
    return member_ids


def _insert_box_set(db, library_id: int, physical: dict) -> int:
    title = str(physical.get("title") or "").strip()
    if not title:
        raise ValueError("Box-set title is required")
    values = {field: physical.get(field) for field in PHYSICAL_FIELDS}
    values["title"] = title
    values["status"] = values.get("status") or "owned"
    cur = db.execute(
        """INSERT INTO box_sets(
            library_id,barcode,title,tmdb_collection_id,poster_path,format,version,country,
            language,region,disc_count,notes,shelf_id,status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (library_id, *[values[field] for field in PHYSICAL_FIELDS]),
    )
    return int(cur.lastrowid)


def create_box_set(db, library_id: int, physical: dict, members: list[dict]) -> int:
    if not members:
        raise ValueError("Select at least one contained film")
    try:
        with db:
            box_id = _insert_box_set(db, library_id, physical)
            member_ids = reconcile_box_set_members(db, library_id, box_id, members)
            if physical.get("tmdb_collection_id"):
                ensure_organizational_collection_for_box_set(db, library_id, int(physical["tmdb_collection_id"]), str(physical.get("title") or "Movie Collection"), member_ids)
        return box_id
    except Exception:
        db.rollback()
        raise


def convert_movie_to_box_set(db, movie, physical: dict, members: list[dict]) -> int:
    """Convert an existing physical movie row into a box-set parent in one transaction."""
    if not members:
        raise ValueError("Select at least one contained film")
    library_id = int(movie["library_id"])
    movie_id = int(movie["id"])
    try:
        with db:
            box_id = _insert_box_set(db, library_id, physical)
            member_ids = reconcile_box_set_members(db, library_id, box_id, members)
            if physical.get("tmdb_collection_id"):
                ensure_organizational_collection_for_box_set(db, library_id, int(physical["tmdb_collection_id"]), str(physical.get("title") or "Movie Collection"), member_ids)
            for loan in db.execute("SELECT * FROM loans WHERE movie_id=? ORDER BY id", (movie_id,)).fetchall():
                db.execute(
                    """INSERT INTO box_set_loans(
                       library_id,box_set_id,borrower_name,phone,loaned_date,returned_date,notes,created_at
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (library_id, box_id, loan["borrower_name"], loan["phone"], loan["loaned_date"],
                     loan["returned_date"], loan["notes"], loan["created_at"]),
                )
            db.execute("DELETE FROM movies WHERE id=? AND library_id=?", (movie_id, library_id))
        return box_id
    except Exception:
        db.rollback()
        raise


def box_set_effective_state(db, box_set_id: int) -> dict:
    whole = db.execute(
        "SELECT * FROM box_set_loans WHERE box_set_id=? AND returned_date IS NULL ORDER BY id DESC LIMIT 1",
        (box_set_id,),
    ).fetchone()
    member_loans = db.execute(
        """SELECT l.*, m.title, m.id AS member_id
           FROM loans l JOIN movies m ON m.id=l.movie_id
           WHERE m.parent_box_set_id=? AND l.returned_date IS NULL
           ORDER BY COALESCE(m.parent_box_set_position,999999),m.id""",
        (box_set_id,),
    ).fetchall()
    return {
        "whole_loan": whole,
        "member_loans": member_loans,
        "incomplete": bool(member_loans),
        "can_loan_whole": whole is None and not member_loans,
        "state": "loaned" if whole else ("incomplete" if member_loans else "available"),
    }


def member_effective_state(db, member_id: int) -> dict:
    member = db.execute("SELECT * FROM movies WHERE id=? AND parent_box_set_id IS NOT NULL", (member_id,)).fetchone()
    if not member:
        return {"state": "missing", "loan": None}
    whole = db.execute(
        "SELECT * FROM box_set_loans WHERE box_set_id=? AND returned_date IS NULL ORDER BY id DESC LIMIT 1",
        (member["parent_box_set_id"],),
    ).fetchone()
    if whole:
        return {"state": "loaned_with_box_set", "loan": whole}
    loan = db.execute(
        "SELECT * FROM loans WHERE movie_id=? AND returned_date IS NULL ORDER BY id DESC LIMIT 1",
        (member_id,),
    ).fetchone()
    if loan:
        return {"state": "loaned_individually", "loan": loan}
    return {"state": "available", "loan": None}


def loan_box_set(db, library_id, box_set_id, borrower_name, phone=None, loaned_date=None, notes=None):
    state = box_set_effective_state(db, box_set_id)
    if state["whole_loan"]:
        raise BoxSetLoanConflict("This box set is already on loan.")
    if state["member_loans"]:
        raise BoxSetLoanConflict("Return all individually loaned films before loaning the whole box set.")
    borrower_name = str(borrower_name or "").strip()
    if not borrower_name:
        raise ValueError("Borrower name is required")
    with db:
        db.execute(
            "INSERT INTO box_set_loans(library_id,box_set_id,borrower_name,phone,loaned_date,notes) VALUES (?,?,?,?,?,?)",
            (library_id, box_set_id, borrower_name, phone or None, loaned_date or date.today().isoformat(), notes or None),
        )


def return_box_set(db, library_id, box_set_id, returned_date=None):
    with db:
        db.execute(
            "UPDATE box_set_loans SET returned_date=? WHERE library_id=? AND box_set_id=? AND returned_date IS NULL",
            (returned_date or date.today().isoformat(), library_id, box_set_id),
        )


def loan_box_set_member(db, library_id, member_id, borrower_name, phone=None, loaned_date=None, notes=None):
    member = db.execute(
        "SELECT * FROM movies WHERE id=? AND library_id=? AND parent_box_set_id IS NOT NULL", (member_id, library_id)
    ).fetchone()
    if not member:
        raise ValueError("Contained film not found")
    state = member_effective_state(db, member_id)
    if state["state"] == "loaned_with_box_set":
        raise BoxSetLoanConflict("The whole box set is already on loan.")
    if state["state"] == "loaned_individually":
        raise BoxSetLoanConflict("This film is already on loan.")
    borrower_name = str(borrower_name or "").strip()
    if not borrower_name:
        raise ValueError("Borrower name is required")
    with db:
        db.execute(
            "INSERT INTO loans(library_id,movie_id,borrower_name,phone,loaned_date,notes) VALUES (?,?,?,?,?,?)",
            (library_id, member_id, borrower_name, phone or None, loaned_date or date.today().isoformat(), notes or None),
        )


def return_box_set_member(db, library_id, member_id, returned_date=None):
    with db:
        db.execute(
            "UPDATE loans SET returned_date=? WHERE library_id=? AND movie_id=? AND returned_date IS NULL",
            (returned_date or date.today().isoformat(), library_id, member_id),
        )


def box_set_has_loan_history(db, box_set_id: int) -> bool:
    direct = db.execute("SELECT 1 FROM box_set_loans WHERE box_set_id=? LIMIT 1", (box_set_id,)).fetchone()
    member = db.execute(
        """SELECT 1 FROM loans l JOIN movies m ON m.id=l.movie_id
           WHERE m.parent_box_set_id=? LIMIT 1""", (box_set_id,)
    ).fetchone()
    legacy = db.execute(
        """SELECT 1 FROM box_set_member_loans bml JOIN box_set_members bsm ON bsm.id=bml.box_set_member_id
           WHERE bsm.box_set_id=? LIMIT 1""", (box_set_id,)
    ).fetchone()
    return bool(direct or member or legacy)
