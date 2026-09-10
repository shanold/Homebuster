from conftest import create_user, login


def test_registration_creates_private_library(client, app):
    response = client.post(
        "/register",
        data={"username": "alice", "password": "verysecurepass", "confirm_password": "verysecurepass"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"My Movies" in response.data
    from movie_catalogue.db import get_db
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE username='alice'").fetchone()
        library = get_db().execute("SELECT * FROM libraries WHERE owner_id=?", (user["id"],)).fetchone()
        assert library["name"] == "My Movies"


def test_registration_can_be_disabled(tmp_path):
    from movie_catalogue import create_app
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "DATABASE_PATH": str(tmp_path / "disabled.db"),
        "SECRET_KEY": "test-secret",
        "ALLOW_REGISTRATION": False,
    })
    client = app.test_client()
    assert client.get("/register").status_code == 404
    assert client.post("/register", data={"username":"x","password":"1234567890","confirm_password":"1234567890"}).status_code == 404


def test_password_reset_invalidates_existing_session(client, app):
    create_user(app, "admin", admin=True)
    create_user(app, "bob")
    bob_client = app.test_client()
    login(bob_client, "bob")
    assert bob_client.get("/libraries").status_code == 200

    login(client, "admin")
    response = client.post("/admin/users/bob/reset-password", data={"new_password": "newsecurepass"}, follow_redirects=True)
    assert response.status_code == 200
    response = bob_client.get("/libraries", follow_redirects=False)
    assert response.status_code in (302, 401)
    assert login(bob_client, "bob", "newsecurepass").status_code == 200


def test_admin_has_no_implicit_library_access(client, app):
    create_user(app, "admin", admin=True)
    _, private_library = create_user(app, "bob")
    login(client, "admin")
    assert client.get(f"/libraries/{private_library}").status_code == 403
