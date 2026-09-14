from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .password_policy import password_length_error


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        try:
            db.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        g.db = db
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def table_columns(db: sqlite3.Connection, name: str) -> set[str]:
    if not table_exists(db, name):
        return set()
    return {row["name"] for row in db.execute(f"PRAGMA table_info({name})").fetchall()}


def _create_identity_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            disabled INTEGER NOT NULL DEFAULT 0,
            auth_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            default_media_type TEXT NOT NULL DEFAULT 'movie',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS idx_libraries_owner ON libraries(owner_id);

        CREATE TABLE IF NOT EXISTS library_members (
            library_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('viewer', 'editor')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(library_id, user_id),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_library_members_user ON library_members(user_id);

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            auth_version INTEGER NOT NULL,
            label TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
        """
    )


def _create_catalog_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS shelves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE,
            description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(library_id, name),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_shelves_library ON shelves(library_id, sort_order, name);

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            barcode TEXT,
            title TEXT NOT NULL,
            year TEXT,
            format TEXT,
            poster_path TEXT,
            tmdb_id INTEGER,
            media_type TEXT NOT NULL DEFAULT 'movie' CHECK(media_type IN ('movie','tv')),
            status TEXT NOT NULL DEFAULT 'owned',
            version TEXT,
            country TEXT,
            language TEXT,
            region TEXT,
            disc_count INTEGER,
            review_pending INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            shelf_id INTEGER,
            parent_box_set_id INTEGER,
            parent_box_set_position INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(shelf_id) REFERENCES shelves(id) ON DELETE SET NULL,
            FOREIGN KEY(parent_box_set_id) REFERENCES box_sets(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_movies_library_title ON movies(library_id, title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_movies_library_status ON movies(library_id, status);
        CREATE INDEX IF NOT EXISTS idx_movies_shelf ON movies(shelf_id);
        CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(library_id, tmdb_id);
        CREATE INDEX IF NOT EXISTS idx_movies_barcode ON movies(library_id, barcode);

        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE,
            UNIQUE(library_id, name),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_collections_library_name ON collections(library_id, name COLLATE NOCASE);

        CREATE TABLE IF NOT EXISTS movie_collections (
            movie_id INTEGER NOT NULL,
            collection_id INTEGER NOT NULL,
            PRIMARY KEY(movie_id, collection_id),
            FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            borrower_name TEXT NOT NULL,
            phone TEXT,
            loaned_date TEXT NOT NULL,
            returned_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_loans_library_active ON loans(library_id, returned_date, loaned_date);
        CREATE INDEX IF NOT EXISTS idx_loans_movie ON loans(movie_id, returned_date);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_loan_per_movie
            ON loans(movie_id) WHERE returned_date IS NULL;

        CREATE TABLE IF NOT EXISTS box_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            barcode TEXT,
            title TEXT NOT NULL,
            tmdb_collection_id INTEGER,
            poster_path TEXT,
            format TEXT,
            version TEXT,
            country TEXT,
            language TEXT,
            region TEXT,
            disc_count INTEGER,
            notes TEXT,
            shelf_id INTEGER,
            status TEXT NOT NULL DEFAULT 'owned',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(shelf_id) REFERENCES shelves(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_box_sets_library_title ON box_sets(library_id, title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_box_sets_barcode ON box_sets(library_id, barcode);
        CREATE INDEX IF NOT EXISTS idx_box_sets_tmdb_collection ON box_sets(library_id, tmdb_collection_id);

        CREATE TABLE IF NOT EXISTS box_set_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            box_set_id INTEGER NOT NULL,
            tmdb_id INTEGER,
            title TEXT NOT NULL,
            year TEXT,
            poster_path TEXT,
            position INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(box_set_id) REFERENCES box_sets(id) ON DELETE CASCADE,
            UNIQUE(box_set_id, tmdb_id)
        );
        CREATE INDEX IF NOT EXISTS idx_box_set_members_box ON box_set_members(box_set_id, position, id);
        CREATE INDEX IF NOT EXISTS idx_box_set_members_title ON box_set_members(title COLLATE NOCASE);

        CREATE TABLE IF NOT EXISTS box_set_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            box_set_id INTEGER NOT NULL,
            borrower_name TEXT NOT NULL,
            phone TEXT,
            loaned_date TEXT NOT NULL,
            returned_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(box_set_id) REFERENCES box_sets(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_loan_per_box_set
            ON box_set_loans(box_set_id) WHERE returned_date IS NULL;

        CREATE TABLE IF NOT EXISTS box_set_member_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            box_set_member_id INTEGER NOT NULL,
            borrower_name TEXT NOT NULL,
            phone TEXT,
            loaned_date TEXT NOT NULL,
            returned_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(box_set_member_id) REFERENCES box_set_members(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_loan_per_box_member
            ON box_set_member_loans(box_set_member_id) WHERE returned_date IS NULL;
        """
    )


def _ensure_catalog_columns(db: sqlite3.Connection) -> None:
    """Add catalog columns introduced after the original multi-library schema."""
    movie_cols = table_columns(db, "movies")
    if movie_cols and "review_pending" not in movie_cols:
        db.execute("ALTER TABLE movies ADD COLUMN review_pending INTEGER NOT NULL DEFAULT 0")
    movie_cols = table_columns(db, "movies")
    if movie_cols and "media_type" not in movie_cols:
        db.execute("ALTER TABLE movies ADD COLUMN media_type TEXT NOT NULL DEFAULT 'movie'")
    movie_cols = table_columns(db, "movies")
    if movie_cols and "parent_box_set_id" not in movie_cols:
        db.execute("ALTER TABLE movies ADD COLUMN parent_box_set_id INTEGER")
    movie_cols = table_columns(db, "movies")
    if movie_cols and "parent_box_set_position" not in movie_cols:
        db.execute("ALTER TABLE movies ADD COLUMN parent_box_set_position INTEGER")
    if movie_cols:
        db.execute("CREATE INDEX IF NOT EXISTS idx_movies_parent_box_set ON movies(parent_box_set_id, parent_box_set_position, id)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_parent_tmdb_unique ON movies(parent_box_set_id, tmdb_id) WHERE parent_box_set_id IS NOT NULL AND tmdb_id IS NOT NULL")
    library_cols = table_columns(db, "libraries")
    if library_cols and "show_box_set_members" not in library_cols:
        db.execute("ALTER TABLE libraries ADD COLUMN show_box_set_members INTEGER NOT NULL DEFAULT 0")
    if library_cols and "default_media_type" not in library_cols:
        db.execute("ALTER TABLE libraries ADD COLUMN default_media_type TEXT NOT NULL DEFAULT 'movie'")



def _migrate_box_set_members_to_movies(db: sqlite3.Connection) -> None:
    """Promote v0.3.27 lightweight box-set members and their loans into first-class movies.

    Legacy tables are retained as rollback/source data, but promotion is deliberately one-time.
    Otherwise a contained film intentionally removed in v0.3.28 would be recreated from the
    old legacy row on the next startup.
    """
    db.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    marker = db.execute("SELECT value FROM app_meta WHERE key='v0328_box_set_member_promotion'").fetchone()
    if marker and str(marker[0]) == "1":
        return
    if not (table_exists(db, "box_sets") and table_exists(db, "box_set_members") and table_exists(db, "movies")):
        return
    if "parent_box_set_id" not in table_columns(db, "movies"):
        return

    members = db.execute(
        """SELECT bsm.*, bs.library_id
           FROM box_set_members bsm JOIN box_sets bs ON bs.id=bsm.box_set_id
           ORDER BY bsm.box_set_id,bsm.position,bsm.id"""
    ).fetchall()
    legacy_to_movie = {}
    for member in members:
        existing = None
        if member["tmdb_id"] is not None:
            existing = db.execute(
                "SELECT id FROM movies WHERE parent_box_set_id=? AND tmdb_id=? AND media_type='movie' ORDER BY id LIMIT 1",
                (member["box_set_id"], member["tmdb_id"]),
            ).fetchone()
        if existing is None:
            existing = db.execute(
                """SELECT id FROM movies WHERE parent_box_set_id=? AND title=? COLLATE NOCASE
                   AND COALESCE(year,'')=COALESCE(?, '') ORDER BY id LIMIT 1""",
                (member["box_set_id"], member["title"], member["year"]),
            ).fetchone()
        if existing:
            movie_id = int(existing["id"] if hasattr(existing, "keys") else existing[0])
            db.execute(
                """UPDATE movies SET tmdb_id=COALESCE(tmdb_id,?), poster_path=COALESCE(poster_path,?),
                   parent_box_set_position=COALESCE(parent_box_set_position,?), updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (member["tmdb_id"], member["poster_path"], member["position"], movie_id),
            )
        else:
            cur = db.execute(
                """INSERT INTO movies(
                    library_id,title,year,poster_path,tmdb_id,media_type,status,review_pending,parent_box_set_id,parent_box_set_position
                ) VALUES (?,?,?,?,?,'movie','owned',0,?,?)""",
                (member["library_id"], member["title"], member["year"], member["poster_path"], member["tmdb_id"],
                 member["box_set_id"], member["position"]),
            )
            movie_id = int(cur.lastrowid)
        legacy_to_movie[int(member["id"])] = movie_id

    if table_exists(db, "box_set_member_loans"):
        for legacy_loan in db.execute("SELECT * FROM box_set_member_loans ORDER BY id").fetchall():
            movie_id = legacy_to_movie.get(int(legacy_loan["box_set_member_id"]))
            if not movie_id:
                continue
            duplicate = db.execute(
                """SELECT 1 FROM loans WHERE movie_id=? AND borrower_name=? AND loaned_date=?
                   AND COALESCE(phone,'')=COALESCE(?, '') AND COALESCE(notes,'')=COALESCE(?, '') LIMIT 1""",
                (movie_id, legacy_loan["borrower_name"], legacy_loan["loaned_date"], legacy_loan["phone"], legacy_loan["notes"]),
            ).fetchone()
            if duplicate:
                continue
            db.execute(
                """INSERT INTO loans(library_id,movie_id,borrower_name,phone,loaned_date,returned_date,notes,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (legacy_loan["library_id"], movie_id, legacy_loan["borrower_name"], legacy_loan["phone"],
                 legacy_loan["loaned_date"], legacy_loan["returned_date"], legacy_loan["notes"], legacy_loan["created_at"]),
            )
    db.execute(
        "INSERT OR REPLACE INTO app_meta(key,value) VALUES ('v0328_box_set_member_promotion','1')"
    )

def _bootstrap_admin(db: sqlite3.Connection) -> None:
    username = (current_app.config.get("INITIAL_ADMIN_USERNAME") or "").strip()
    password = current_app.config.get("INITIAL_ADMIN_PASSWORD") or ""
    if not username or not password:
        return
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        return
    if error := password_length_error(password, current_app.config, label="INITIAL_ADMIN_PASSWORD"):
        raise RuntimeError(error)
    cur = db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
        (username, generate_password_hash(password)),
    )
    db.execute("INSERT INTO libraries (name, owner_id) VALUES ('My Movies', ?)", (cur.lastrowid,))
    db.commit()


def _choose_migration_library(db: sqlite3.Connection) -> int:
    row = db.execute(
        """
        SELECT l.id
        FROM libraries l
        JOIN users u ON u.id=l.owner_id
        ORDER BY u.is_admin DESC, u.id ASC, l.id ASC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        raise RuntimeError(
            "Legacy movies.db detected, but no user exists to own the imported Library. "
            "Set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD for the first startup, "
            "or run the create-admin Flask command before migration."
        )
    return int(row["id"])


def backup_database(label: str = "backup") -> Path | None:
    db = get_db()
    db.commit()
    db_path = Path(current_app.config["DATABASE_PATH"])
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = backup_dir / f"{label}-{stamp}.db"
    dest = sqlite3.connect(destination)
    try:
        db.backup(dest)
    finally:
        dest.close()
    return destination


def _legacy_value(row: sqlite3.Row, columns: set[str], name: str, default=None):
    return row[name] if name in columns else default


def _migrate_legacy(db: sqlite3.Connection) -> None:
    movie_cols = table_columns(db, "movies")
    if not movie_cols or "library_id" in movie_cols:
        return

    library_id = _choose_migration_library(db)
    backup_database("pre-migration")

    has_collections = table_exists(db, "collections")
    has_links = table_exists(db, "movie_collections")

    db.execute("ALTER TABLE movies RENAME TO legacy_movies")
    if has_collections:
        db.execute("ALTER TABLE collections RENAME TO legacy_collections")
    if has_links:
        db.execute("ALTER TABLE movie_collections RENAME TO legacy_movie_collections")
    db.commit()

    _create_catalog_tables(db)

    legacy_movie_cols = table_columns(db, "legacy_movies")
    rows = db.execute("SELECT * FROM legacy_movies ORDER BY rowid").fetchall()
    for row in rows:
        legacy_id = _legacy_value(row, legacy_movie_cols, "rowid")
        if legacy_id is None:
            legacy_id = row["id"] if "id" in legacy_movie_cols else None
        db.execute(
            """
            INSERT INTO movies (
                id, library_id, barcode, title, year, format, poster_path, tmdb_id, status,
                version, country, language, region, disc_count, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                legacy_id,
                library_id,
                _legacy_value(row, legacy_movie_cols, "barcode"),
                _legacy_value(row, legacy_movie_cols, "title", "Untitled"),
                _legacy_value(row, legacy_movie_cols, "year"),
                _legacy_value(row, legacy_movie_cols, "format"),
                _legacy_value(row, legacy_movie_cols, "poster_path"),
                _legacy_value(row, legacy_movie_cols, "tmdb_id"),
                _legacy_value(row, legacy_movie_cols, "status", "owned") or "owned",
                _legacy_value(row, legacy_movie_cols, "version"),
                _legacy_value(row, legacy_movie_cols, "country"),
                _legacy_value(row, legacy_movie_cols, "language"),
                _legacy_value(row, legacy_movie_cols, "region"),
                _legacy_value(row, legacy_movie_cols, "disc_count"),
                _legacy_value(row, legacy_movie_cols, "notes"),
            ),
        )

    if table_exists(db, "legacy_collections"):
        for row in db.execute("SELECT id, name FROM legacy_collections ORDER BY id").fetchall():
            db.execute(
                "INSERT INTO collections (id, library_id, name) VALUES (?, ?, ?)",
                (row["id"], library_id, row["name"]),
            )

    if table_exists(db, "legacy_movie_collections"):
        link_cols = table_columns(db, "legacy_movie_collections")
        movie_column = "movie_rowid" if "movie_rowid" in link_cols else "movie_id"
        for row in db.execute(
            f"SELECT {movie_column} AS movie_id, collection_id FROM legacy_movie_collections"
        ).fetchall():
            db.execute(
                "INSERT OR IGNORE INTO movie_collections (movie_id, collection_id) VALUES (?, ?)",
                (row["movie_id"], row["collection_id"]),
            )

    db.execute("DROP TABLE legacy_movies")
    if table_exists(db, "legacy_movie_collections"):
        db.execute("DROP TABLE legacy_movie_collections")
    if table_exists(db, "legacy_collections"):
        db.execute("DROP TABLE legacy_collections")
    db.commit()


def initialize_database() -> None:
    db = get_db()
    _create_identity_tables(db)
    db.commit()
    _bootstrap_admin(db)
    _migrate_legacy(db)
    _create_catalog_tables(db)
    _ensure_catalog_columns(db)
    _migrate_box_set_members_to_movies(db)
    db.commit()


@click.command("create-admin")
@click.argument("username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_admin_command(username: str, password: str) -> None:
    if error := password_length_error(password, current_app.config):
        raise click.ClickException(error)
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        db.execute(
            "UPDATE users SET password_hash=?, is_admin=1, disabled=0, auth_version=auth_version+1 WHERE id=?",
            (generate_password_hash(password), existing["id"]),
        )
        db.commit()
        click.echo(f"Homebuster updated {username} and granted site-admin access.")
        return
    cur = db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
        (username, generate_password_hash(password)),
    )
    db.execute("INSERT INTO libraries (name, owner_id) VALUES ('My Movies', ?)", (cur.lastrowid,))
    db.commit()
    click.echo(f"Homebuster created site admin {username}.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(create_admin_command)
