from movie_catalogue.db import get_db


def _login(client, username="alice", password="verysecurepass"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "device_name": "pytest"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_existing_web_login_route_still_exists(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Homebuster" in response.data


def test_mobile_login_returns_token(client, app):
    from conftest import create_user
    create_user(app, "alice")
    headers = _login(client)
    assert headers["Authorization"].startswith("Bearer ")


def test_mobile_lists_existing_library_and_movies(client, app):
    from conftest import create_user
    _, library_id = create_user(app, "alice")
    headers = _login(client)
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO movies (library_id,title,year,format,barcode) VALUES (?,?,?,?,?)",
            (library_id, "Alien", "1979", "Blu-ray", "024543627421"),
        )
        db.commit()
    response = client.get("/api/v1/movies", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["movies"][0]["title"] == "Alien"


def test_barcode_prefers_existing_owned_copy(client, app):
    from conftest import create_user
    _, library_id = create_user(app, "alice")
    headers = _login(client)
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO movies (library_id,title,year,format,barcode) VALUES (?,?,?,?,?)",
            (library_id, "Alien", "1979", "Blu-ray", "024543627421"),
        )
        db.commit()
    response = client.get("/api/v1/barcodes/024543627421", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["status"] == "owned"


def test_api_token_revoked_when_auth_version_changes(client, app):
    from conftest import create_user
    create_user(app, "alice")
    headers = _login(client)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET auth_version=auth_version+1 WHERE username='alice'")
        db.commit()
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
