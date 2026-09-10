import os
import tempfile
import pytest

from app import create_app

@pytest.fixture()
def client():
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret',
        'PASSWORD_MIN_LENGTH': 8,
        'TMDB_API_KEY': '',
        'UPCITEMDB_API_KEY': '',
    })
    with app.test_client() as c:
        yield c
    os.unlink(db_path)


def register_and_login(client):
    r = client.post('/api/v1/auth/register', json={'username':'alice','password':'password1'})
    assert r.status_code == 201
    r = client.post('/api/v1/auth/login', json={'username':'alice','password':'password1'})
    assert r.status_code == 200
    token = r.get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_mobile_login_returns_bearer_token(client):
    headers = register_and_login(client)
    assert headers['Authorization'].startswith('Bearer ')


def test_movies_are_scoped_to_logged_in_user(client):
    h = register_and_login(client)
    r = client.post('/api/v1/movies', headers=h, json={'title':'Alien','year':1979,'format':'Blu-ray','upc':'024543627421'})
    assert r.status_code == 201
    r = client.get('/api/v1/movies', headers=h)
    assert r.status_code == 200
    movies = r.get_json()['movies']
    assert len(movies) == 1
    assert movies[0]['title'] == 'Alien'


def test_barcode_lookup_prefers_existing_local_copy(client):
    h = register_and_login(client)
    client.post('/api/v1/movies', headers=h, json={'title':'Alien','year':1979,'format':'Blu-ray','upc':'024543627421'})
    r = client.get('/api/v1/barcodes/024543627421', headers=h)
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'owned'
    assert data['movie']['title'] == 'Alien'


def test_unknown_barcode_without_provider_is_clean_404(client):
    h = register_and_login(client)
    r = client.get('/api/v1/barcodes/012345678905', headers=h)
    assert r.status_code == 404
    assert r.get_json()['status'] == 'not_found'


def test_password_min_length_applies_to_api_registration(client):
    r = client.post('/api/v1/auth/register', json={'username':'bob','password':'short'})
    assert r.status_code == 400
    assert '8' in r.get_json()['error']
