import sqlite3, importlib.util
spec=importlib.util.spec_from_file_location('smart_collections','movie_catalogue/smart_collections.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
suggestions,approve,dismiss,restore,sync_physical_box_set_collection=(mod.suggestions,mod.approve,mod.dismiss,mod.restore,mod.sync_physical_box_set_collection)

db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row
db.executescript('''
create table libraries(id integer primary key, smart_collections_enabled integer not null default 1);
create table movies(id integer primary key,library_id integer,tmdb_id integer,media_type text,parent_box_set_id integer);
create table collections(id integer primary key autoincrement,library_id integer,name text,tmdb_collection_id integer,tmdb_collection_name text,tmdb_last_refreshed_at text,unique(library_id,name));
create unique index idx on collections(library_id,tmdb_collection_id) where tmdb_collection_id is not null;
create table movie_collections(movie_id integer,collection_id integer,primary key(movie_id,collection_id));
create table tmdb_movie_collection_cache(tmdb_movie_id integer primary key,tmdb_collection_id integer,tmdb_collection_name text,checked_at text);
create table tmdb_collection_cache(tmdb_collection_id integer primary key,tmdb_collection_name text,released_count integer,checked_at text);
create table smart_collection_dismissals(library_id integer,tmdb_collection_id integer,dismissed_at text default current_timestamp,primary key(library_id,tmdb_collection_id));
insert into libraries values(1,1);
''')
def seed(cid,total,owned):
 db.execute('insert into tmdb_collection_cache values(?,?,?,CURRENT_TIMESTAMP)',(cid,f'C{cid}',total))
 for i in range(owned):
  mid=cid*100+i; db.execute("insert into movies values(?,?,?,'movie',null)",(mid,1,mid)); db.execute('insert into tmdb_movie_collection_cache values(?,?,?,CURRENT_TIMESTAMP)',(mid,cid,f'C{cid}'))
seed(1,3,2); seed(2,4,2); seed(3,9,2); seed(4,9,5); db.commit()
assert [x['tmdb_collection_id'] for x in suggestions(db,1)] == [1,2,4]
dismiss(db,1,1); assert 1 not in [x['tmdb_collection_id'] for x in suggestions(db,1)]; assert 1 in [x['tmdb_collection_id'] for x in suggestions(db,1,True)]
restore(db,1,1); assert 1 in [x['tmdb_collection_id'] for x in suggestions(db,1)]
cid=approve(db,1,1); assert db.execute('select count(*) from movie_collections where collection_id=?',(cid,)).fetchone()[0]==2
sync_physical_box_set_collection(db,1,99,'Harry Potter',[100,101]); assert db.execute('select count(*) from movie_collections mc join collections c on c.id=mc.collection_id where c.tmdb_collection_id=99').fetchone()[0]==2
db.execute('update libraries set smart_collections_enabled=0 where id=1'); assert suggestions(db,1)==[]
# a newly owned identified movie joins an already approved TMDb-backed collection
newmid=199; db.execute("insert into movies values(?,?,?,'movie',null)",(newmid,1,newmid)); mod.auto_link_movie(db,1,newmid,newmid,{'id':1,'name':'C1'}); assert db.execute('select 1 from movie_collections where movie_id=? and collection_id=?',(newmid,cid)).fetchone()
# released denominator ignores future parts and collection refresh is throttled for 24h
calls=[]
def fetch(cid):
 calls.append(cid); return {'title':'Future Test','parts':[{'id':1,'release_date':'2020-01-01'},{'id':2,'release_date':'2999-01-01'}]}
mod.refresh_collection_cache(db,[77],fetch); assert db.execute('select released_count from tmdb_collection_cache where tmdb_collection_id=77').fetchone()[0]==1
mod.refresh_collection_cache(db,[77],fetch); assert calls==[77]
print('v0.3.41 smart collection behavior checks passed')
