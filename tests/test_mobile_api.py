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


def test_barcode_returns_structured_metadata_and_ranked_match(client, app, monkeypatch):
    from conftest import create_user
    from movie_catalogue import mobile_api

    create_user(app, "alice")
    headers = _login(client)
    monkeypatch.setattr(mobile_api, "barcode_product_lookup", lambda upc: {
        "upc": upc,
        "product_title": "Spider-Man [DVD] English Sony Pictures Home Entertainment Special Edition 2002",
        "search_title": "Spider-Man",
        "fallback_title": "Spider-Man English Sony Pictures Home Entertainment",
        "search_year": 2002,
        "detected_formats": ["DVD"],
        "detected_format": "DVD",
        "detected_edition": "Special Edition",
        "detected_language": "English",
        "detected_region": None,
        "detected_disc_count": None,
        "detected_distributor": "Sony Pictures Home Entertainment",
    })
    monkeypatch.setattr(mobile_api, "tmdb_search", lambda query, year=None: [
        {"tmdb_id": 2, "title": "Spider-Man 2", "year": 2004, "overview": "", "poster_path": None},
        {"tmdb_id": 1, "title": "Spider-Man", "year": 2002, "overview": "", "poster_path": None},
    ])

    response = client.get("/api/v1/barcodes/024543627421", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["lookup"]["title"] == "Spider-Man"
    assert payload["lookup"]["language"] == "English"
    assert payload["lookup"]["edition"] == "Special Edition"
    assert payload["lookup"]["distributor"] == "Sony Pictures Home Entertainment"
    assert payload["best_match"]["tmdb_id"] == 1
    assert payload["tmdb_results"][0]["tmdb_id"] == 1


def test_mobile_add_movie_persists_detected_physical_metadata(client, app):
    from conftest import create_user

    _, library_id = create_user(app, "alice")
    headers = _login(client)
    response = client.post("/api/v1/movies", headers=headers, json={
        "library_id": library_id,
        "tmdb_id": 1,
        "title": "Spider-Man",
        "year": 2002,
        "format": "DVD",
        "upc": "024543627421",
        "version": "Special Edition",
        "language": "English",
        "region": "Region 1",
        "disc_count": 2,
    })
    assert response.status_code == 201
    movie = response.get_json()["movie"]
    assert movie["version"] == "Special Edition"
    assert movie["language"] == "English"
    assert movie["region"] == "Region 1"
    assert movie["disc_count"] == 2
