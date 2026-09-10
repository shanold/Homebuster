from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


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
            status TEXT NOT NULL DEFAULT 'owned',
            version TEXT,
            country TEXT,
            language TEXT,
            region TEXT,
            disc_count INTEGER,
            notes TEXT,
            shelf_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
            FOREIGN KEY(shelf_id) REFERENCES shelves(id) ON DELETE SET NULL
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
        """
    )


def _bootstrap_admin(db: sqlite3.Connection) -> None:
    username = (current_app.config.get("INITIAL_ADMIN_USERNAME") or "").strip()
    password = current_app.config.get("INITIAL_ADMIN_PASSWORD") or ""
    if not username or not password:
        return
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        return
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
    db.commit()


@click.command("create-admin")
@click.argument("username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_admin_command(username: str, password: str) -> None:
    if len(password) < 10:
        raise click.ClickException("Password must be at least 10 characters.")
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        db.execute(
            "UPDATE users SET password_hash=?, is_admin=1, disabled=0, auth_version=auth_version+1 WHERE id=?",
            (generate_password_hash(password), existing["id"]),
        )
        db.commit()
        click.echo(f"Updated {username} and granted site-admin access.")
        return
    cur = db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
        (username, generate_password_hash(password)),
    )
    db.execute("INSERT INTO libraries (name, owner_id) VALUES ('My Movies', ?)", (cur.lastrowid,))
    db.commit()
    click.echo(f"Created site admin {username}.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(create_admin_command)
