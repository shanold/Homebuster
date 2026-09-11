from movie_catalogue.catalog import _group_movie_rows, _high_confidence_match, _tmdb_poster_url


def test_tmdb_poster_path_is_normalized(app):
    with app.app_context():
        assert _tmdb_poster_url('/castle.jpg') == 'https://image.tmdb.org/t/p/w342/castle.jpg'
        assert _tmdb_poster_url('https://image.tmdb.org/t/p/w500/castle.jpg') == 'https://image.tmdb.org/t/p/w500/castle.jpg'


def test_grouping_combines_same_tmdb_id_but_not_unmatched():
    rows = [
        {'id': 1, 'tmdb_id': 10515, 'title': 'Castle in the Sky', 'format': 'Blu-ray', 'poster_path': None, 'active_loan_id': None},
        {'id': 2, 'tmdb_id': 10515, 'title': 'Castle in the Sky', 'format': 'DVD', 'poster_path': 'https://x/poster.jpg', 'active_loan_id': None},
        {'id': 3, 'tmdb_id': None, 'title': 'Unknown', 'format': 'DVD', 'poster_path': None, 'active_loan_id': None},
        {'id': 4, 'tmdb_id': None, 'title': 'Unknown', 'format': 'DVD', 'poster_path': None, 'active_loan_id': None},
    ]
    groups = _group_movie_rows(rows)
    assert len(groups) == 3
    castle = groups[0]
    assert castle['copy_count'] == 2
    assert castle['poster_path'] == 'https://x/poster.jpg'
    assert set(castle['formats']) == {'Blu-ray', 'DVD'}


def test_high_confidence_requires_clear_match():
    exact = [
        {'tmdb_id': 1, 'title': 'Castle in the Sky', 'year': 1986},
        {'tmdb_id': 2, 'title': 'Castle in the Sky 2', 'year': 2000},
    ]
    assert _high_confidence_match('Castle in the Sky', '1986', exact)['tmdb_id'] == 1

    ambiguous = [
        {'tmdb_id': 3, 'title': 'Crash', 'year': 1996},
        {'tmdb_id': 4, 'title': 'Crash', 'year': 2004},
    ]
    assert _high_confidence_match('Crash', None, ambiguous) is None


def test_scanner_add_normalizes_poster(client, app, monkeypatch):
    from tests.conftest import create_user
    from movie_catalogue.db import get_db
    user_id, library_id = create_user(app, 'mobileuser')
    with app.app_context():
        db = get_db()
        token = 'test-token'
        import hashlib
        db.execute('INSERT INTO api_tokens (user_id, token_hash, name) VALUES (?,?,?)', (user_id, hashlib.sha256(token.encode()).hexdigest(), 'test'))
        db.commit()
    response = client.post('/api/v1/movies', headers={'Authorization': 'Bearer test-token'}, json={
        'library_id': library_id, 'title': 'Castle in the Sky', 'year': 1986,
        'format': 'Blu-ray', 'tmdb_id': 10515, 'poster_path': '/castle.jpg'
    })
    assert response.status_code == 201
    with app.app_context():
        row = get_db().execute('SELECT poster_path FROM movies WHERE library_id=?', (library_id,)).fetchone()
        assert row['poster_path'] == 'https://image.tmdb.org/t/p/w342/castle.jpg'
