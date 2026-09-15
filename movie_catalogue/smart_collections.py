from __future__ import annotations
from datetime import date, datetime, timezone

REFRESH_HOURS = 24
BACKFILL_BATCH = 10
COLLECTION_REFRESH_BATCH = 3


def _fresh(ts, hours=REFRESH_HOURS):
    if not ts: return False
    try:
        dt=datetime.fromisoformat(str(ts).replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc)-dt).total_seconds() < hours*3600
    except Exception: return False


def cache_movie_membership(db, tmdb_movie_id, relation):
    cid = int(relation['id']) if relation and relation.get('id') else None
    name = relation.get('name') if relation else None
    db.execute("""INSERT INTO tmdb_movie_collection_cache(tmdb_movie_id,tmdb_collection_id,tmdb_collection_name,checked_at)
                  VALUES (?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(tmdb_movie_id) DO UPDATE SET
                  tmdb_collection_id=excluded.tmdb_collection_id,tmdb_collection_name=excluded.tmdb_collection_name,checked_at=CURRENT_TIMESTAMP""",
               (int(tmdb_movie_id),cid,name))


def backfill_memberships(db, library_id, fetch_movie_details, limit=BACKFILL_BATCH):
    rows=db.execute("""SELECT DISTINCT m.tmdb_id FROM movies m LEFT JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id
                       WHERE m.library_id=? AND m.media_type='movie' AND m.tmdb_id IS NOT NULL AND c.tmdb_movie_id IS NULL LIMIT ?""",(library_id,limit)).fetchall()
    checked=0
    for row in rows:
        mid=int(row[0])
        try: details=fetch_movie_details(mid)
        except Exception: continue
        if details is None: continue
        cache_movie_membership(db,mid,details.get('belongs_to_collection')); checked+=1
    db.commit()
    remaining=db.execute("""SELECT COUNT(DISTINCT m.tmdb_id) FROM movies m LEFT JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id
                            WHERE m.library_id=? AND m.media_type='movie' AND m.tmdb_id IS NOT NULL AND c.tmdb_movie_id IS NULL""",(library_id,)).fetchone()[0]
    return checked,int(remaining)


def _released_count(details):
    today=date.today().isoformat()
    return len({int(p['id']) for p in (details or {}).get('parts',[]) if p.get('id') and p.get('release_date') and p['release_date'] <= today})


def refresh_collection_cache(db, collection_ids, fetch_collection_details, limit=COLLECTION_REFRESH_BATCH):
    refreshed=0
    for cid in list(dict.fromkeys(int(x) for x in collection_ids if x)):
        row=db.execute("SELECT checked_at FROM tmdb_collection_cache WHERE tmdb_collection_id=?",(cid,)).fetchone()
        if row and _fresh(row[0]): continue
        if refreshed >= limit: break
        try: details=fetch_collection_details(cid)
        except Exception: continue
        if not details: continue
        name=details.get('title') or 'Collection'; count=_released_count(details)
        db.execute("""INSERT INTO tmdb_collection_cache(tmdb_collection_id,tmdb_collection_name,released_count,checked_at)
                      VALUES (?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(tmdb_collection_id) DO UPDATE SET
                      tmdb_collection_name=excluded.tmdb_collection_name,released_count=excluded.released_count,checked_at=CURRENT_TIMESTAMP""",(cid,name,count))
        db.execute("UPDATE collections SET tmdb_collection_name=?,tmdb_last_refreshed_at=CURRENT_TIMESTAMP WHERE tmdb_collection_id=?",(name,cid))
        refreshed+=1
    db.commit(); return refreshed


def suggestions(db, library_id, show_dismissed=False):
    lib=db.execute("SELECT smart_collections_enabled FROM libraries WHERE id=?",(library_id,)).fetchone()
    if not lib or not int(lib[0]): return []
    rows=db.execute("""SELECT c.tmdb_collection_id, COALESCE(cc.tmdb_collection_name,c.tmdb_collection_name) name,
                              COUNT(DISTINCT m.tmdb_id) owned, COALESCE(cc.released_count,0) released,
                              CASE WHEN d.tmdb_collection_id IS NULL THEN 0 ELSE 1 END dismissed
                       FROM movies m JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id
                       LEFT JOIN tmdb_collection_cache cc ON cc.tmdb_collection_id=c.tmdb_collection_id
                       LEFT JOIN smart_collection_dismissals d ON d.library_id=m.library_id AND d.tmdb_collection_id=c.tmdb_collection_id
                       LEFT JOIN collections approved ON approved.library_id=m.library_id AND approved.tmdb_collection_id=c.tmdb_collection_id
                       WHERE m.library_id=? AND m.media_type='movie' AND c.tmdb_collection_id IS NOT NULL AND approved.id IS NULL
                       GROUP BY c.tmdb_collection_id
                       HAVING owned>=2 AND released>0 AND (owned*1.0/released)>=0.5
                       ORDER BY name COLLATE NOCASE""",(library_id,)).fetchall()
    return [dict(r) for r in rows if show_dismissed or not int(r['dismissed'])]


def ensure_collection(db, library_id, tmdb_collection_id, name):
    row=db.execute("SELECT id FROM collections WHERE library_id=? AND tmdb_collection_id=?",(library_id,tmdb_collection_id)).fetchone()
    if row: return int(row[0])
    # Never infer identity from an existing manual collection name: create a distinct, safely named backed collection.
    candidate=name or 'Collection'; suffix=2
    while db.execute("SELECT 1 FROM collections WHERE library_id=? AND name=? COLLATE NOCASE",(library_id,candidate)).fetchone():
        candidate=f"{name} (TMDb {suffix})"; suffix+=1
    cur=db.execute("INSERT INTO collections(library_id,name,tmdb_collection_id,tmdb_collection_name) VALUES (?,?,?,?)",(library_id,candidate,int(tmdb_collection_id),name))
    return int(cur.lastrowid)


def link_owned_movies(db, library_id, collection_id, tmdb_collection_id):
    db.execute("""INSERT OR IGNORE INTO movie_collections(movie_id,collection_id)
                  SELECT m.id,? FROM movies m JOIN tmdb_movie_collection_cache c ON c.tmdb_movie_id=m.tmdb_id
                  WHERE m.library_id=? AND m.media_type='movie' AND c.tmdb_collection_id=?""",(collection_id,library_id,int(tmdb_collection_id)))


def approve(db, library_id, tmdb_collection_id):
    row=db.execute("SELECT tmdb_collection_name FROM tmdb_collection_cache WHERE tmdb_collection_id=?",(tmdb_collection_id,)).fetchone()
    if not row: row=db.execute("SELECT tmdb_collection_name FROM tmdb_movie_collection_cache WHERE tmdb_collection_id=? LIMIT 1",(tmdb_collection_id,)).fetchone()
    name=(row[0] if row else None) or 'TMDb Collection'
    cid=ensure_collection(db,library_id,tmdb_collection_id,name); link_owned_movies(db,library_id,cid,tmdb_collection_id)
    db.execute("DELETE FROM smart_collection_dismissals WHERE library_id=? AND tmdb_collection_id=?",(library_id,tmdb_collection_id)); db.commit(); return cid


def dismiss(db, library_id, tmdb_collection_id):
    db.execute("INSERT OR IGNORE INTO smart_collection_dismissals(library_id,tmdb_collection_id) VALUES (?,?)",(library_id,int(tmdb_collection_id))); db.commit()


def restore(db, library_id, tmdb_collection_id):
    db.execute("DELETE FROM smart_collection_dismissals WHERE library_id=? AND tmdb_collection_id=?",(library_id,int(tmdb_collection_id))); db.commit()


def auto_link_movie(db, library_id, movie_id, tmdb_movie_id, relation=None):
    if not tmdb_movie_id: return
    if relation is not None: cache_movie_membership(db,tmdb_movie_id,relation)
    row=db.execute("SELECT tmdb_collection_id FROM tmdb_movie_collection_cache WHERE tmdb_movie_id=?",(tmdb_movie_id,)).fetchone()
    if not row or not row[0]: return
    collections=db.execute("SELECT id FROM collections WHERE library_id=? AND tmdb_collection_id=?",(library_id,int(row[0]))).fetchall()
    for c in collections: db.execute("INSERT OR IGNORE INTO movie_collections(movie_id,collection_id) VALUES (?,?)",(movie_id,int(c[0])))


def sync_physical_box_set_collection(db, library_id, tmdb_collection_id, name, member_ids):
    if not tmdb_collection_id: return None
    cid=ensure_collection(db,library_id,int(tmdb_collection_id),name or 'Movie Collection')
    for mid in member_ids: db.execute("INSERT OR IGNORE INTO movie_collections(movie_id,collection_id) VALUES (?,?)",(int(mid),cid))
    return cid
