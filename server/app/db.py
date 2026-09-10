import sqlite3
from flask import current_app, g

SCHEMA = r'''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS api_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL DEFAULT 'Android',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS libraries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  is_private INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shelves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS movies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  shelf_id INTEGER REFERENCES shelves(id) ON DELETE SET NULL,
  tmdb_id INTEGER,
  title TEXT NOT NULL,
  year INTEGER,
  overview TEXT NOT NULL DEFAULT '',
  poster_path TEXT,
  runtime INTEGER,
  media_format TEXT NOT NULL DEFAULT 'Unknown',
  upc TEXT,
  watched INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_movies_library ON movies(library_id);
CREATE INDEX IF NOT EXISTS idx_movies_upc ON movies(upc);
CREATE TABLE IF NOT EXISTS collection_movies (
  collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
  PRIMARY KEY(collection_id, movie_id)
);
CREATE TABLE IF NOT EXISTS loans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
  borrower TEXT NOT NULL,
  loaned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  returned_at TEXT,
  notes TEXT NOT NULL DEFAULT ''
);
'''

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(_e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()

def ensure_default_library(user_id):
    db = get_db()
    row = db.execute('SELECT id FROM libraries WHERE user_id=? ORDER BY id LIMIT 1', (user_id,)).fetchone()
    if row:
        return row['id']
    cur = db.execute('INSERT INTO libraries(user_id,name,is_private) VALUES(?,?,1)', (user_id, 'My Library'))
    db.commit()
    return cur.lastrowid
