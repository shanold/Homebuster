import sqlite3, sys, importlib.util
from datetime import date, datetime, timedelta, timezone
spec=importlib.util.spec_from_file_location('smart_collections','movie_catalogue/smart_collections.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for name in [n for n in dir(m) if not n.startswith('_')]: globals()[name]=getattr(m,name)

def db():
 d=sqlite3.connect(':memory:'); d.row_factory=sqlite3.Row
 d.executescript('''CREATE TABLE libraries(id INTEGER PRIMARY KEY,smart_collections_enabled INTEGER DEFAULT 1); CREATE TABLE movies(id INTEGER PRIMARY KEY,library_id INTEGER,tmdb_id INTEGER,media_type TEXT,parent_box_set_id INTEGER); CREATE TABLE collections(id INTEGER PRIMARY KEY AUTOINCREMENT,library_id INTEGER,name TEXT,tmdb_collection_id INTEGER,tmdb_collection_name TEXT,tmdb_last_refreshed_at TEXT); CREATE UNIQUE INDEX u ON collections(library_id,tmdb_collection_id) WHERE tmdb_collection_id IS NOT NULL; CREATE TABLE movie_collections(movie_id INTEGER,collection_id INTEGER,PRIMARY KEY(movie_id,collection_id)); CREATE TABLE tmdb_movie_collection_cache(tmdb_movie_id INTEGER PRIMARY KEY,tmdb_collection_id INTEGER,tmdb_collection_name TEXT,checked_at TEXT); CREATE TABLE smart_collection_parts(tmdb_collection_id INTEGER,tmdb_movie_id INTEGER,title TEXT,release_date TEXT,PRIMARY KEY(tmdb_collection_id,tmdb_movie_id)); CREATE TABLE smart_collection_refresh_state(tmdb_collection_id INTEGER PRIMARY KEY,refreshed_at TEXT); CREATE TABLE smart_collection_dismissals(library_id INTEGER,tmdb_collection_id INTEGER,dismissed_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(library_id,tmdb_collection_id));'''); d.execute('insert into libraries values(1,1)'); return d

d=db()
for i in range(1,4): d.execute('insert into smart_collection_parts values(99,?,?,?)',(i,f'M{i}','2020-01-01'))
for rid,tid in [(1,1),(2,2),(3,2)]: d.execute("insert into movies values(?,?,?,'movie',NULL)",(rid,1,tid))
for tid in (1,2): cache_movie_collection_membership(d,tid,{'id':99,'name':'Example Collection'})
s=get_smart_collection_suggestions(d,1,today=date(2026,1,1)); assert len(s)==1 and s[0]['owned_count']==2 and s[0]['released_count']==3
# duplicates don't inflate; dismissal/restore; approval idempotent
dismiss_smart_collection(d,1,99); assert not get_smart_collection_suggestions(d,1,today=date(2026,1,1)); assert get_smart_collection_suggestions(d,1,True,date(2026,1,1))[0]['dismissed']
restore_smart_collection(d,1,99); cid=approve_smart_collection(d,1,99); assert cid==approve_smart_collection(d,1,99); assert d.execute('select count(*) from movie_collections').fetchone()[0]==3
# future auto-link
d.execute("insert into movies values(4,1,3,'movie',NULL)"); cache_movie_collection_membership(d,3,{'id':99,'name':'Example Collection'}); assert auto_link_movie_to_approved_collection(d,4)==cid
# explicit box set sync links only supplied movie ids
cid2=ensure_organizational_collection_for_box_set(d,1,100,'Other Collection',[1,2]); assert d.execute('select count(*) from collections where tmdb_collection_id=100').fetchone()[0]==1
# disabled means no suggestions
d.execute('update libraries set smart_collections_enabled=0 where id=1'); assert get_smart_collection_suggestions(d,1,today=date(2026,1,1))==[]
print('v0.3.41 smart collections behavior passed')

# bounded backfill and 24-hour refresh throttle
d2=db(); [d2.execute("insert into movies values(?,?,?,'movie',NULL)",(i,1,100+i)) for i in range(1,11)]
calls=[]
def fm(mid): calls.append(mid); return {'belongs_to_collection': {'id':200,'name':'Ten'}}
r=backfill_uncached_movie_memberships(d2,1,fm,limit=8); assert len(calls)==8 and r['unchecked_movies']==2
refresh_calls=[]
def fc(cid): refresh_calls.append(cid); return {'title':'Ten','parts':[{'id':101,'title':'A','release_date':'2020-01-01'}]}
r=refresh_known_collections(d2,1,fc,now=datetime(2026,1,2,tzinfo=timezone.utc),limit=2); assert r['refreshed']==1
r=refresh_known_collections(d2,1,fc,now=datetime(2026,1,2,12,tzinfo=timezone.utc),limit=2); assert r['refreshed']==0 and len(refresh_calls)==1
