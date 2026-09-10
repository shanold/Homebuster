import sqlite3


def test_legacy_database_migrates_movies_and_collections(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
    CREATE TABLE movies (
      rowid INTEGER PRIMARY KEY,
      barcode TEXT,
      title TEXT NOT NULL,
      year TEXT,
      format TEXT,
      poster_path TEXT,
      tmdb_id INTEGER,
      status TEXT,
      version TEXT,
      country TEXT,
      language TEXT,
      region TEXT,
      disc_count INTEGER,
      notes TEXT
    );
    CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
    CREATE TABLE movie_collections (movie_rowid INTEGER NOT NULL, collection_id INTEGER NOT NULL, PRIMARY KEY(movie_rowid, collection_id));
    INSERT INTO movies(rowid,title,format,status) VALUES (42,'Evil Dead II','Blu-ray','owned');
    INSERT INTO collections(id,name) VALUES (7,'Evil Dead');
    INSERT INTO movie_collections(movie_rowid,collection_id) VALUES (42,7);
    """)
    conn.commit(); conn.close()

    from movie_catalogue import create_app
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "DATABASE_PATH": str(db_path),
        "SECRET_KEY":"x",
        "INITIAL_ADMIN_USERNAME":"admin",
        "INITIAL_ADMIN_PASSWORD":"verysecurepass",
    })
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        movie = db.execute("SELECT * FROM movies WHERE id=42").fetchone()
        collection = db.execute("SELECT * FROM collections WHERE id=7").fetchone()
        link = db.execute("SELECT * FROM movie_collections WHERE movie_id=42 AND collection_id=7").fetchone()
        assert movie["title"] == "Evil Dead II"
        assert collection["name"] == "Evil Dead"
        assert link is not None
