from __future__ import annotations

from datetime import date


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
        "SELECT * FROM box_set_members WHERE box_set_id=? ORDER BY position,id",
        (box_set_id,),
    ).fetchall()


def create_box_set(db, library_id: int, physical: dict, members: list[dict]) -> int:
    title = str(physical.get("title") or "").strip()
    if not title:
        raise ValueError("Box-set title is required")
    if not members:
        raise ValueError("Select at least one contained film")
    values = {field: physical.get(field) for field in PHYSICAL_FIELDS}
    values["title"] = title
    values["status"] = values.get("status") or "owned"
    try:
        with db:
            cur = db.execute(
                """INSERT INTO box_sets(
                    library_id,barcode,title,tmdb_collection_id,poster_path,format,version,country,
                    language,region,disc_count,notes,shelf_id,status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (library_id, *[values[field] for field in PHYSICAL_FIELDS]),
            )
            box_id = int(cur.lastrowid)
            for position, member in enumerate(members):
                member_title = str(member.get("title") or "").strip()
                if not member_title:
                    raise ValueError("Every box-set member needs a title")
                db.execute(
                    """INSERT INTO box_set_members(box_set_id,tmdb_id,title,year,poster_path,position)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        box_id, member.get("tmdb_id"), member_title,
                        str(member.get("year")) if member.get("year") not in (None, "") else None,
                        member.get("poster_path"), int(member.get("position", position)),
                    ),
                )
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
        """SELECT bml.*, bsm.title, bsm.id AS member_id
           FROM box_set_member_loans bml JOIN box_set_members bsm ON bsm.id=bml.box_set_member_id
           WHERE bsm.box_set_id=? AND bml.returned_date IS NULL ORDER BY bsm.position,bsm.id""",
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
    member = db.execute("SELECT * FROM box_set_members WHERE id=?", (member_id,)).fetchone()
    if not member:
        return {"state": "missing", "loan": None}
    whole = db.execute(
        "SELECT * FROM box_set_loans WHERE box_set_id=? AND returned_date IS NULL ORDER BY id DESC LIMIT 1",
        (member["box_set_id"],),
    ).fetchone()
    if whole:
        return {"state": "loaned_with_box_set", "loan": whole}
    loan = db.execute(
        "SELECT * FROM box_set_member_loans WHERE box_set_member_id=? AND returned_date IS NULL ORDER BY id DESC LIMIT 1",
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
        """SELECT bsm.*,bs.library_id FROM box_set_members bsm JOIN box_sets bs ON bs.id=bsm.box_set_id
           WHERE bsm.id=? AND bs.library_id=?""", (member_id, library_id)
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
            "INSERT INTO box_set_member_loans(library_id,box_set_member_id,borrower_name,phone,loaned_date,notes) VALUES (?,?,?,?,?,?)",
            (library_id, member_id, borrower_name, phone or None, loaned_date or date.today().isoformat(), notes or None),
        )


def return_box_set_member(db, library_id, member_id, returned_date=None):
    with db:
        db.execute(
            "UPDATE box_set_member_loans SET returned_date=? WHERE library_id=? AND box_set_member_id=? AND returned_date IS NULL",
            (returned_date or date.today().isoformat(), library_id, member_id),
        )


def box_set_has_loan_history(db, box_set_id: int) -> bool:
    direct = db.execute("SELECT 1 FROM box_set_loans WHERE box_set_id=? LIMIT 1", (box_set_id,)).fetchone()
    member = db.execute(
        """SELECT 1 FROM box_set_member_loans bml JOIN box_set_members bsm ON bsm.id=bml.box_set_member_id
           WHERE bsm.box_set_id=? LIMIT 1""", (box_set_id,)
    ).fetchone()
    return bool(direct or member)
