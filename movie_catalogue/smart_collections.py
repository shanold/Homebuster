from __future__ import annotations
from datetime import date, datetime, timezone, timedelta


def _now(now=None): return now or datetime.now(timezone.utc)
def _text(now=None): return _now(now).replace(microsecond=0).isoformat()

def cache_movie_collection_membership(db, tmdb_movie_id, relationship):
    cid = int(relationship['id']) if relationship and relationship.get('id') is not None else None
    name = relationship.get('name') if relationship else None
    db.execute('INSERT INTO tmdb_movie_collection_cache(tmdb_movie_id,tmdb_collection_id,tmdb_collection_name,checked_at) VALUES(?,?,?,?) ON CONFLICT(tmdb_movie_id) DO UPDATE SET tmdb_collection_id=excluded.tmdb_collection_id,tmdb_collection_name=excluded.tmdb_collection_name,checked_at=excluded.checked_at',(int(tmdb_movie_id),cid,name,_text()))

def _released_ids(db,cid,today=None):
    today=today or date.today(); out=[]
    for r in db.execute('SELECT tmdb_movie_id,release_date FROM smart_collection_parts WHERE tmdb_collection_id=?',(cid,)):
        rd=r['release_date'] if hasattr(r,'keys') else r[1]
        if rd and rd[:10] <= today.isoformat(): out.append(int(r['tmdb_movie_id'] if hasattr(r,'keys') else r[0]))
    return set(out)

def get_smart_collection_suggestions(db, library_id, show_dismissed=False, today=None):
    lib=db.execute('SELECT smart_collections_enabled FROM libraries WHERE id=?',(library_id,)).fetchone()
    if not lib or not int(lib[0]): return []
    rows=db.execute('SELECT DISTINCT c.tmdb_collection_id,c.tmdb_collection_name FROM tmdb_movie_collection_cache c JOIN movies m ON m.tmdb_id=c.tmdb_movie_id WHERE m.library_id=? AND m.media_type=\'movie\' AND c.tmdb_collection_id IS NOT NULL',(library_id,)).fetchall(); result=[]
    for r in rows:
        cid=int(r[0]); name=r[1] or f'TMDb Collection {cid}'
        if db.execute('SELECT 1 FROM collections WHERE library_id=? AND tmdb_collection_id=?',(library_id,cid)).fetchone(): continue
        released=_released_ids(db,cid,today)
        if not released: continue
        owned={int(x[0]) for x in db.execute("SELECT DISTINCT m.tmdb_id FROM movies m JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id WHERE m.library_id=? AND m.media_type='movie' AND c.tmdb_collection_id=?",(library_id,cid)).fetchall() if x[0] is not None} & released
        if len(owned)<2 or len(owned)/len(released)<0.5: continue
        dismissed=bool(db.execute('SELECT 1 FROM smart_collection_dismissals WHERE library_id=? AND tmdb_collection_id=?',(library_id,cid)).fetchone())
        if dismissed and not show_dismissed: continue
        result.append({'tmdb_collection_id':cid,'name':name,'owned_count':len(owned),'released_count':len(released),'dismissed':dismissed})
    return sorted(result,key=lambda x:x['name'].lower())

def dismiss_smart_collection(db,library_id,tmdb_collection_id): db.execute('INSERT OR REPLACE INTO smart_collection_dismissals(library_id,tmdb_collection_id,dismissed_at) VALUES(?,?,?)',(library_id,tmdb_collection_id,_text()))
def restore_smart_collection(db,library_id,tmdb_collection_id): db.execute('DELETE FROM smart_collection_dismissals WHERE library_id=? AND tmdb_collection_id=?',(library_id,tmdb_collection_id))

def _get_or_create(db,library_id,cid,name):
    r=db.execute('SELECT id FROM collections WHERE library_id=? AND tmdb_collection_id=?',(library_id,cid)).fetchone()
    if r:return int(r[0])
    base=name or f'TMDb Collection {cid}'; candidate=base; n=2
    while db.execute('SELECT 1 FROM collections WHERE library_id=? AND name=? COLLATE NOCASE',(library_id,candidate)).fetchone(): candidate=f'{base} (TMDb {n})'; n+=1
    cur=db.execute('INSERT INTO collections(library_id,name,tmdb_collection_id,tmdb_collection_name) VALUES(?,?,?,?)',(library_id,candidate,cid,name or base)); return int(cur.lastrowid)

def approve_smart_collection(db,library_id,tmdb_collection_id):
    r=db.execute('SELECT tmdb_collection_name FROM tmdb_movie_collection_cache WHERE tmdb_collection_id=? AND tmdb_collection_name IS NOT NULL LIMIT 1',(tmdb_collection_id,)).fetchone(); name=r[0] if r else f'TMDb Collection {tmdb_collection_id}'
    cid=_get_or_create(db,library_id,tmdb_collection_id,name)
    db.execute("INSERT OR IGNORE INTO movie_collections(movie_id,collection_id) SELECT m.id,? FROM movies m JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id WHERE m.library_id=? AND m.media_type='movie' AND c.tmdb_collection_id=?",(cid,library_id,tmdb_collection_id)); restore_smart_collection(db,library_id,tmdb_collection_id); return cid

def auto_link_movie_to_approved_collection(db,movie_id):
    r=db.execute("SELECT m.library_id,c.tmdb_collection_id FROM movies m JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id WHERE m.id=? AND m.media_type='movie'",(movie_id,)).fetchone()
    if not r or r[1] is None:return None
    c=db.execute('SELECT id FROM collections WHERE library_id=? AND tmdb_collection_id=?',(r[0],r[1])).fetchone()
    if not c:return None
    db.execute('INSERT OR IGNORE INTO movie_collections(movie_id,collection_id) VALUES(?,?)',(movie_id,c[0])); return int(c[0])

def ensure_organizational_collection_for_box_set(db,library_id,tmdb_collection_id,name,member_movie_ids):
    cid=_get_or_create(db,library_id,int(tmdb_collection_id),name)
    for mid in member_movie_ids: db.execute('INSERT OR IGNORE INTO movie_collections(movie_id,collection_id) VALUES(?,?)',(int(mid),cid))
    return cid

def backfill_uncached_movie_memberships(db,library_id,fetch_movie_details,limit=8):
    ids=[int(r[0]) for r in db.execute("SELECT DISTINCT m.tmdb_id FROM movies m LEFT JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id WHERE m.library_id=? AND m.media_type='movie' AND m.tmdb_id IS NOT NULL AND c.tmdb_movie_id IS NULL LIMIT ?",(library_id,limit)).fetchall()]
    done=0
    for mid in ids:
        try: d=fetch_movie_details(mid)
        except Exception: continue
        if d is None: continue
        cache_movie_collection_membership(db,mid,d.get('belongs_to_collection'))
        for row in db.execute("SELECT id FROM movies WHERE library_id=? AND media_type='movie' AND tmdb_id=?",(library_id,mid)).fetchall(): auto_link_movie_to_approved_collection(db,int(row[0]))
        done+=1
    left=db.execute("SELECT COUNT(DISTINCT m.tmdb_id) FROM movies m LEFT JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id WHERE m.library_id=? AND m.media_type='movie' AND m.tmdb_id IS NOT NULL AND c.tmdb_movie_id IS NULL",(library_id,)).fetchone()[0]
    return {'processed':done,'unchecked_movies':int(left)}

def refresh_known_collections(db,library_id,fetch_collection_details,now=None,limit=2):
    now=_now(now); cids={int(r[0]) for r in db.execute("SELECT DISTINCT c.tmdb_collection_id FROM tmdb_movie_collection_cache c JOIN movies m ON m.tmdb_id=c.tmdb_movie_id WHERE m.library_id=? AND c.tmdb_collection_id IS NOT NULL",(library_id,))}
    cids.update(int(r[0]) for r in db.execute("SELECT tmdb_collection_id FROM collections WHERE library_id=? AND tmdb_collection_id IS NOT NULL",(library_id,)).fetchall())
    refreshed=0
    for cid in sorted(cids):
        if refreshed>=limit: break
        row=db.execute('SELECT refreshed_at FROM smart_collection_refresh_state WHERE tmdb_collection_id=?',(cid,)).fetchone()
        stamp=row[0] if row else None
        if stamp:
            try:
                if now-datetime.fromisoformat(stamp) < timedelta(hours=24): continue
            except Exception: pass
        try: details=fetch_collection_details(cid)
        except Exception: continue
        if not details: continue
        db.execute('DELETE FROM smart_collection_parts WHERE tmdb_collection_id=?',(cid,))
        for p in details.get('parts') or []:
            if p.get('id') is not None: db.execute('INSERT OR REPLACE INTO smart_collection_parts VALUES(?,?,?,?)',(cid,int(p['id']),p.get('title'),p.get('release_date') or ''))
        db.execute('INSERT OR REPLACE INTO smart_collection_refresh_state(tmdb_collection_id,refreshed_at) VALUES(?,?)',(cid,_text(now)))
        db.execute('UPDATE collections SET tmdb_collection_name=?,tmdb_last_refreshed_at=? WHERE library_id=? AND tmdb_collection_id=?',(details.get('title'),_text(now),library_id,cid))
        refreshed+=1
    return {'refreshed':refreshed}
