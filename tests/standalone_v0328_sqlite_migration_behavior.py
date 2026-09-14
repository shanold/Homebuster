import ast, sqlite3
from pathlib import Path

src=Path('movie_catalogue/db.py').read_text()
tree=ast.parse(src)
wanted={'table_exists','table_columns','_create_catalog_tables','_ensure_catalog_columns','_migrate_box_set_members_to_movies'}
body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]
body += [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
mod=ast.Module(body=body,type_ignores=[]); ast.fix_missing_locations(mod)
ns={'sqlite3':sqlite3}
exec(compile(mod,'db_extract','exec'),ns)

# Minimal v0.3.27-style database.
db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
db.executescript('''
CREATE TABLE users(id INTEGER PRIMARY KEY);
CREATE TABLE libraries(id INTEGER PRIMARY KEY,name TEXT,owner_id INTEGER,created_at TEXT,show_box_set_members INTEGER NOT NULL DEFAULT 0);
CREATE TABLE shelves(id INTEGER PRIMARY KEY,library_id INTEGER,name TEXT,description TEXT,sort_order INTEGER DEFAULT 0);
CREATE TABLE movies(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER NOT NULL,barcode TEXT,title TEXT NOT NULL,year TEXT,format TEXT,poster_path TEXT,tmdb_id INTEGER,media_type TEXT NOT NULL DEFAULT 'movie',status TEXT NOT NULL DEFAULT 'owned',version TEXT,country TEXT,language TEXT,region TEXT,disc_count INTEGER,review_pending INTEGER NOT NULL DEFAULT 0,notes TEXT,shelf_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE collections(id INTEGER PRIMARY KEY,library_id INTEGER,name TEXT);
CREATE TABLE movie_collections(movie_id INTEGER,collection_id INTEGER,PRIMARY KEY(movie_id,collection_id));
CREATE TABLE loans(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER NOT NULL,movie_id INTEGER NOT NULL,borrower_name TEXT NOT NULL,phone TEXT,loaned_date TEXT NOT NULL,returned_date TEXT,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE box_sets(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER NOT NULL,barcode TEXT,title TEXT NOT NULL,tmdb_collection_id INTEGER,poster_path TEXT,format TEXT,version TEXT,country TEXT,language TEXT,region TEXT,disc_count INTEGER,notes TEXT,shelf_id INTEGER,status TEXT DEFAULT 'owned',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE box_set_members(id INTEGER PRIMARY KEY AUTOINCREMENT,box_set_id INTEGER NOT NULL,tmdb_id INTEGER,title TEXT NOT NULL,year TEXT,poster_path TEXT,position INTEGER NOT NULL DEFAULT 0,UNIQUE(box_set_id,tmdb_id));
CREATE TABLE box_set_loans(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER NOT NULL,box_set_id INTEGER NOT NULL,borrower_name TEXT NOT NULL,phone TEXT,loaned_date TEXT NOT NULL,returned_date TEXT,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE box_set_member_loans(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER NOT NULL,box_set_member_id INTEGER NOT NULL,borrower_name TEXT NOT NULL,phone TEXT,loaned_date TEXT NOT NULL,returned_date TEXT,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT INTO libraries(id,name,owner_id) VALUES(1,'Test',1);
INSERT INTO box_sets(id,library_id,title,tmdb_collection_id,format) VALUES(10,1,'Harry Potter Collection',1241,'Blu-ray');
INSERT INTO box_set_members(id,box_set_id,tmdb_id,title,year,poster_path,position) VALUES(100,10,671,'Harry Potter and the Philosopher''s Stone','2001','/hp1.jpg',0);
INSERT INTO box_set_members(id,box_set_id,tmdb_id,title,year,poster_path,position) VALUES(101,10,672,'Harry Potter and the Chamber of Secrets','2002','/hp2.jpg',1);
INSERT INTO box_set_member_loans(id,library_id,box_set_member_id,borrower_name,phone,loaned_date,notes) VALUES(50,1,101,'Sam','555','2026-09-01','test');
''')
ns['_create_catalog_tables'](db)
ns['_ensure_catalog_columns'](db)
ns['_migrate_box_set_members_to_movies'](db)
db.commit()
cols=ns['table_columns'](db,'movies')
assert {'parent_box_set_id','parent_box_set_position'} <= cols
kids=db.execute('SELECT * FROM movies WHERE parent_box_set_id=10 ORDER BY parent_box_set_position').fetchall()
assert [k['tmdb_id'] for k in kids]==[671,672]
assert kids[1]['id'] == db.execute('SELECT movie_id FROM loans WHERE borrower_name=?',('Sam',)).fetchone()[0]
# Idempotency, including after the promoted loan is returned. The retained legacy
# source row must never resurrect an already-returned loan on the next startup.
ns['_migrate_box_set_members_to_movies'](db); db.commit()
assert db.execute('SELECT COUNT(*) FROM movies WHERE parent_box_set_id=10').fetchone()[0]==2
assert db.execute('SELECT COUNT(*) FROM loans WHERE borrower_name=?',('Sam',)).fetchone()[0]==1
db.execute("UPDATE loans SET returned_date='2026-09-14' WHERE borrower_name='Sam'"); db.commit()
ns['_migrate_box_set_members_to_movies'](db); db.commit()
assert db.execute('SELECT COUNT(*) FROM loans WHERE borrower_name=?',('Sam',)).fetchone()[0]==1
assert db.execute('SELECT returned_date FROM loans WHERE borrower_name=?',('Sam',)).fetchone()[0]=='2026-09-14'
print('v0.3.28 SQLite migration behavior passed')
