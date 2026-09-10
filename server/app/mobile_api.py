import hashlib
import secrets
from functools import wraps
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db, ensure_default_library
from .integrations import barcode_product_lookup, tmdb_search

bp = Blueprint('mobile_api', __name__, url_prefix='/api/v1')

def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def _json_error(message, status=400, **extra):
    data = {'error': message, **extra}
    return jsonify(data), status

def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return _json_error('Authentication required', 401)
        token = auth[7:].strip()
        db = get_db()
        row = db.execute('''SELECT u.* FROM api_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=?''', (_token_hash(token),)).fetchone()
        if not row:
            return _json_error('Invalid or expired token', 401)
        g.api_user = row
        db.execute('UPDATE api_tokens SET last_used_at=CURRENT_TIMESTAMP WHERE token_hash=?', (_token_hash(token),))
        db.commit()
        return view(*args, **kwargs)
    return wrapped

def _movie_row(row):
    return {
        'id': row['id'], 'library_id': row['library_id'], 'shelf_id': row['shelf_id'],
        'tmdb_id': row['tmdb_id'], 'title': row['title'], 'year': row['year'],
        'overview': row['overview'], 'poster_path': row['poster_path'], 'runtime': row['runtime'],
        'format': row['media_format'], 'upc': row['upc'], 'watched': bool(row['watched'])
    }

@bp.get('/health')
def health():
    return jsonify({'name':'Homebuster','api_version':'v1','status':'ok'})

@bp.post('/auth/register')
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username','')).strip()
    password = str(data.get('password',''))
    minimum = int(current_app.config.get('PASSWORD_MIN_LENGTH', 8))
    if len(username) < 2:
        return _json_error('Username must be at least 2 characters')
    if len(password) < minimum:
        return _json_error(f'Password must be at least {minimum} characters')
    db = get_db()
    try:
        cur = db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)', (username, generate_password_hash(password)))
        user_id = cur.lastrowid
        ensure_default_library(user_id)
        db.commit()
    except Exception as e:
        if 'UNIQUE' in str(e).upper():
            return _json_error('Username is already in use', 409)
        raise
    return jsonify({'id':user_id,'username':username}), 201

@bp.post('/auth/login')
def login():
    data = request.get_json(silent=True) or {}
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE', (str(data.get('username','')).strip(),)).fetchone()
    if not user or not check_password_hash(user['password_hash'], str(data.get('password',''))):
        return _json_error('Invalid username or password', 401)
    token = secrets.token_urlsafe(32)
    db.execute('INSERT INTO api_tokens(user_id,token_hash,label) VALUES(?,?,?)', (user['id'], _token_hash(token), str(data.get('device_name') or 'Android')[:80]))
    db.commit()
    return jsonify({'token':token,'user':{'id':user['id'],'username':user['username'],'is_admin':bool(user['is_admin'])}})

@bp.post('/auth/logout')
@token_required
def logout():
    token = request.headers['Authorization'][7:].strip()
    db = get_db(); db.execute('DELETE FROM api_tokens WHERE token_hash=?', (_token_hash(token),)); db.commit()
    return '', 204

@bp.get('/me')
@token_required
def me():
    u=g.api_user
    return jsonify({'id':u['id'],'username':u['username'],'is_admin':bool(u['is_admin'])})

@bp.get('/libraries')
@token_required
def libraries():
    rows=get_db().execute('SELECT id,name,is_private FROM libraries WHERE user_id=? ORDER BY name',(g.api_user['id'],)).fetchall()
    return jsonify({'libraries':[{'id':r['id'],'name':r['name'],'is_private':bool(r['is_private'])} for r in rows]})

@bp.get('/shelves')
@token_required
def shelves():
    rows=get_db().execute('''SELECT s.id,s.library_id,s.name FROM shelves s JOIN libraries l ON l.id=s.library_id WHERE l.user_id=? ORDER BY s.name''',(g.api_user['id'],)).fetchall()
    return jsonify({'shelves':[dict(r) for r in rows]})

@bp.get('/collections')
@token_required
def collections():
    rows=get_db().execute('''SELECT c.id,c.library_id,c.name,c.description,COUNT(cm.movie_id) movie_count FROM collections c JOIN libraries l ON l.id=c.library_id LEFT JOIN collection_movies cm ON cm.collection_id=c.id WHERE l.user_id=? GROUP BY c.id ORDER BY c.name''',(g.api_user['id'],)).fetchall()
    return jsonify({'collections':[dict(r) for r in rows]})

@bp.get('/collections/<int:collection_id>/movies')
@token_required
def collection_movies(collection_id):
    rows=get_db().execute('''SELECT m.* FROM movies m JOIN collection_movies cm ON cm.movie_id=m.id JOIN collections c ON c.id=cm.collection_id JOIN libraries l ON l.id=c.library_id WHERE c.id=? AND l.user_id=? ORDER BY m.title''',(collection_id,g.api_user['id'])).fetchall()
    return jsonify({'movies':[_movie_row(r) for r in rows]})

@bp.get('/movies')
@token_required
def movies():
    db=get_db(); args=[g.api_user['id']]
    sql='''SELECT m.* FROM movies m JOIN libraries l ON l.id=m.library_id WHERE l.user_id=?'''
    q=request.args.get('q','').strip()
    if q:
        sql += ' AND m.title LIKE ?'; args.append(f'%{q}%')
    fmt=request.args.get('format','').strip()
    if fmt:
        sql += ' AND m.media_format=?'; args.append(fmt)
    library=request.args.get('library_id',type=int)
    if library:
        sql += ' AND m.library_id=?'; args.append(library)
    sql += ' ORDER BY m.title COLLATE NOCASE'
    rows=db.execute(sql,args).fetchall()
    return jsonify({'movies':[_movie_row(r) for r in rows]})

@bp.get('/movies/<int:movie_id>')
@token_required
def movie_detail(movie_id):
    row=get_db().execute('''SELECT m.* FROM movies m JOIN libraries l ON l.id=m.library_id WHERE m.id=? AND l.user_id=?''',(movie_id,g.api_user['id'])).fetchone()
    if not row:return _json_error('Movie not found',404)
    return jsonify({'movie':_movie_row(row)})

@bp.post('/movies')
@token_required
def add_movie():
    data=request.get_json(silent=True) or {}; title=str(data.get('title','')).strip()
    if not title:return _json_error('Title is required')
    db=get_db(); library_id=data.get('library_id') or ensure_default_library(g.api_user['id'])
    owns=db.execute('SELECT 1 FROM libraries WHERE id=? AND user_id=?',(library_id,g.api_user['id'])).fetchone()
    if not owns:return _json_error('Library not found',404)
    cur=db.execute('''INSERT INTO movies(library_id,shelf_id,tmdb_id,title,year,overview,poster_path,runtime,media_format,upc,watched) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
        library_id,data.get('shelf_id'),data.get('tmdb_id'),title,data.get('year'),data.get('overview') or '',data.get('poster_path'),data.get('runtime'),data.get('format') or 'Unknown',str(data.get('upc') or '').strip() or None,1 if data.get('watched') else 0))
    db.commit(); row=db.execute('SELECT * FROM movies WHERE id=?',(cur.lastrowid,)).fetchone()
    return jsonify({'movie':_movie_row(row)}),201

@bp.get('/loans')
@token_required
def loans():
    rows=get_db().execute('''SELECT lo.id,lo.movie_id,m.title,lo.borrower,lo.loaned_at,lo.returned_at,lo.notes FROM loans lo JOIN movies m ON m.id=lo.movie_id JOIN libraries l ON l.id=m.library_id WHERE l.user_id=? ORDER BY lo.returned_at IS NOT NULL, lo.loaned_at DESC''',(g.api_user['id'],)).fetchall()
    return jsonify({'loans':[dict(r) for r in rows]})

@bp.get('/tmdb/search')
@token_required
def tmdb_lookup():
    q=request.args.get('q','').strip()
    if not q:return jsonify({'results':[]})
    try:return jsonify({'results':tmdb_search(q)})
    except Exception as exc:return _json_error(f'TMDb lookup failed: {exc}',502)

@bp.get('/barcodes/<upc>')
@token_required
def barcode_lookup(upc):
    upc=''.join(ch for ch in upc if ch.isdigit())
    if len(upc) not in (8,12,13,14): return _json_error('Unsupported barcode',400)
    db=get_db()
    existing=db.execute('''SELECT m.* FROM movies m JOIN libraries l ON l.id=m.library_id WHERE l.user_id=? AND m.upc=? ORDER BY m.id LIMIT 1''',(g.api_user['id'],upc)).fetchone()
    if existing:return jsonify({'status':'owned','movie':_movie_row(existing)})
    try: product=barcode_product_lookup(upc)
    except Exception as exc:return _json_error(f'Barcode provider failed: {exc}',502,provider_status='provider_error')
    if not product:return jsonify({'status':'not_found','upc':upc}),404
    matches=tmdb_search(product['search_title'])
    return jsonify({'status':'product_match','upc':upc,'product':product,'tmdb_results':matches})
