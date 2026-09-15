import ast, sqlite3
from pathlib import Path
src=Path('movie_catalogue/box_set_service.py').read_text(); tree=ast.parse(src)
body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),ast.ImportFrom(module='datetime',names=[ast.alias(name='date')],level=0)]
for n in tree.body:
    if isinstance(n,(ast.Assign,ast.ClassDef,ast.FunctionDef)):
        body.append(n)
mod=ast.Module(body=body,type_ignores=[]); ast.fix_missing_locations(mod); ns={}; exec(compile(mod,'svc','exec'),ns)
db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
db.executescript('''
CREATE TABLE box_sets(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER,barcode TEXT,title TEXT,tmdb_collection_id INTEGER,poster_path TEXT,format TEXT,version TEXT,country TEXT,language TEXT,region TEXT,disc_count INTEGER,notes TEXT,shelf_id INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE shelves(id INTEGER PRIMARY KEY,name TEXT);
CREATE TABLE movies(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER,barcode TEXT,title TEXT,year TEXT,format TEXT,poster_path TEXT,tmdb_id INTEGER,media_type TEXT,status TEXT,version TEXT,country TEXT,language TEXT,region TEXT,disc_count INTEGER,review_pending INTEGER DEFAULT 0,notes TEXT,shelf_id INTEGER,parent_box_set_id INTEGER,parent_box_set_position INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE UNIQUE INDEX uq ON movies(parent_box_set_id,tmdb_id) WHERE parent_box_set_id IS NOT NULL AND tmdb_id IS NOT NULL;
CREATE TABLE loans(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER,movie_id INTEGER,borrower_name TEXT,phone TEXT,loaned_date TEXT,returned_date TEXT,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE UNIQUE INDEX one_loan ON loans(movie_id) WHERE returned_date IS NULL;
CREATE TABLE box_set_loans(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER,box_set_id INTEGER,borrower_name TEXT,phone TEXT,loaned_date TEXT,returned_date TEXT,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE UNIQUE INDEX one_box ON box_set_loans(box_set_id) WHERE returned_date IS NULL;
CREATE TABLE box_set_members(id INTEGER PRIMARY KEY,box_set_id INTEGER);
CREATE TABLE box_set_member_loans(id INTEGER PRIMARY KEY,box_set_member_id INTEGER);
''')
physical={'title':'Harry Potter Collection','tmdb_collection_id':1241,'format':'Blu-ray','status':'owned'}
members=[{'tmdb_id':671,'title':'Harry Potter 1','year':'2001','position':0},{'tmdb_id':672,'title':'Harry Potter 2','year':'2002','position':1}]
box=ns['create_box_set'](db,1,physical,members)
kids=ns['get_box_set_members'](db,box); assert len(kids)==2
# Reconcile same members: no duplicates
ns['reconcile_box_set_members'](db,1,box,members); db.commit(); assert len(ns['get_box_set_members'](db,box))==2
child=kids[0]['id']
ns['loan_box_set_member'](db,1,child,'Alex','555','2026-09-14','note')
state=ns['box_set_effective_state'](db,box); assert state['incomplete'] and not state['can_loan_whole']
try: ns['loan_box_set'](db,1,box,'Jordan')
except ns['BoxSetLoanConflict']: pass
else: raise AssertionError('whole-set loan should be blocked by child loan')
ns['return_box_set_member'](db,1,child)
ns['loan_box_set'](db,1,box,'Jordan')
assert ns['member_effective_state'](db,child)['state']=='loaned_with_box_set'
try: ns['loan_box_set_member'](db,1,child,'Alex')
except ns['BoxSetLoanConflict']: pass
else: raise AssertionError('child loan should be blocked by whole-set loan')

# Converting an old physical movie row to a collection preserves its normal loan history
# as parent box-set loan history and removes the source inventory row atomically.
db.execute("INSERT INTO movies(library_id,barcode,title,format,media_type,status) VALUES (1,'999','Harry Potter 8-Film Collection','Blu-ray','movie','owned')")
source_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
db.execute("INSERT INTO loans(library_id,movie_id,borrower_name,phone,loaned_date,notes) VALUES (1,?,'Taylor','123','2026-08-01','old loan')",(source_id,)); db.commit()
source=db.execute('SELECT * FROM movies WHERE id=?',(source_id,)).fetchone()
box2=ns['convert_movie_to_box_set'](db,source,physical,members)
assert db.execute('SELECT 1 FROM movies WHERE id=?',(source_id,)).fetchone() is None
assert len(ns['get_box_set_members'](db,box2))==2
moved=db.execute('SELECT * FROM box_set_loans WHERE box_set_id=?',(box2,)).fetchone(); assert moved and moved['borrower_name']=='Taylor'

print('v0.3.28 first-class box-set loan behavior passed')
