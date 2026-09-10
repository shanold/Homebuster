from conftest import create_user, login


def test_shelf_assignment_and_filter(client, app):
    _, library_id = create_user(app, "owner")
    login(client, "owner")
    client.post(f"/libraries/{library_id}/shelves", data={"name":"Living Room Shelf 1"}, follow_redirects=True)
    from movie_catalogue.db import get_db
    with app.app_context():
        shelf = get_db().execute("SELECT id FROM shelves WHERE library_id=?", (library_id,)).fetchone()
        shelf_id = shelf["id"]
    client.post(f"/libraries/{library_id}/movies/new", data={"title":"Jaws", "shelf_id":str(shelf_id), "format":"4K", "status":"owned"}, follow_redirects=True)
    response = client.get(f"/libraries/{library_id}?shelf={shelf_id}")
    assert b"Jaws" in response.data


def test_loan_and_return_keeps_history(client, app):
    _, library_id = create_user(app, "owner")
    login(client, "owner")
    client.post(f"/libraries/{library_id}/movies/new", data={"title":"The Matrix", "format":"Blu-ray", "status":"owned"})
    from movie_catalogue.db import get_db
    with app.app_context():
        movie_id = get_db().execute("SELECT id FROM movies WHERE library_id=?", (library_id,)).fetchone()["id"]
    response = client.post(f"/libraries/{library_id}/movies/{movie_id}/loan", data={"borrower_name":"Steve", "phone":"555-1212", "loaned_date":"2026-09-10"}, follow_redirects=True)
    assert b"Steve" in response.data
    client.post(f"/libraries/{library_id}/movies/{movie_id}/return", follow_redirects=True)
    with app.app_context():
        loan = get_db().execute("SELECT * FROM loans WHERE movie_id=?", (movie_id,)).fetchone()
        assert loan["returned_date"] is not None


def test_collection_grouping_is_library_scoped(client, app):
    _, library_id = create_user(app, "owner")
    login(client, "owner")
    client.post(f"/libraries/{library_id}/collections", data={"name":"Evil Dead"}, follow_redirects=True)
    from movie_catalogue.db import get_db
    with app.app_context():
        collection_id = get_db().execute("SELECT id FROM collections WHERE library_id=?", (library_id,)).fetchone()["id"]
    client.post(f"/libraries/{library_id}/movies/new", data={"title":"Evil Dead II", "collection_ids":[str(collection_id)]}, follow_redirects=True)
    response = client.get(f"/libraries/{library_id}?collection={collection_id}")
    assert b"Evil Dead II" in response.data


def test_csv_export_is_scoped_to_library(client, app):
    _, library_id = create_user(app, "owner")
    login(client, "owner")
    client.post(f"/libraries/{library_id}/movies/new", data={"title":"Jaws", "format":"4K", "status":"owned"})
    response = client.get(f"/libraries/{library_id}/export.csv")
    assert response.status_code == 200
    assert b"Jaws" in response.data
    assert b"barcode,title,year" in response.data


def test_add_movie_starts_with_tmdb_lookup(client, app, monkeypatch):
    _, library_id = create_user(app, "lookupowner")
    login(client, "lookupowner")
    app.config["TMDB_API_KEY"] = "test-key"

    from movie_catalogue import catalog
    monkeypatch.setattr(catalog, "_tmdb_search", lambda title, year=None: [{
        "id": 557,
        "title": "Spider-Man",
        "release_date": "2002-05-01",
        "poster_path": "/spider.jpg",
        "overview": "Peter Parker becomes Spider-Man.",
    }])

    response = client.get(f"/libraries/{library_id}/movies/new?q=spiderman")
    assert response.status_code == 200
    assert b"Search TMDb" in response.data
    assert b"Spider-Man" in response.data
    assert b"Use this movie" in response.data


def test_tmdb_selection_prefills_manual_add_form(client, app, monkeypatch):
    _, library_id = create_user(app, "prefillowner")
    login(client, "prefillowner")
    app.config["TMDB_API_KEY"] = "test-key"

    from movie_catalogue import catalog
    monkeypatch.setattr(catalog, "_tmdb_details", lambda tmdb_id: {
        "id": tmdb_id,
        "title": "Spider-Man",
        "release_date": "2002-05-01",
        "poster_path": "/spider.jpg",
        "original_language": "en",
        "production_countries": [{"name": "United States of America"}],
    })

    response = client.get(f"/libraries/{library_id}/movies/new/manual?tmdb_id=557")
    assert response.status_code == 200
    assert b'value="Spider-Man"' in response.data
    assert b'value="2002"' in response.data
    assert b'value="557"' in response.data
    assert b"image.tmdb.org" in response.data
    assert b"Add Movie" in response.data


def test_manual_add_is_available_without_tmdb_key(client, app):
    _, library_id = create_user(app, "manualowner")
    login(client, "manualowner")
    app.config["TMDB_API_KEY"] = ""

    response = client.get(f"/libraries/{library_id}/movies/new")
    assert response.status_code == 200
    assert b"TMDb lookup is unavailable" in response.data
    assert b"Add manually" in response.data
