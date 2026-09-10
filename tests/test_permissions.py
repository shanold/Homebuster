from conftest import create_user, login


def test_viewer_cannot_add_movie(client, app):
    owner_id, library_id = create_user(app, "owner")
    viewer_id, _ = create_user(app, "viewer")
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO library_members (library_id,user_id,role) VALUES (?,?,?)", (library_id, viewer_id, "viewer"))
        db.commit()
    login(client, "viewer")
    assert client.post(f"/libraries/{library_id}/movies/new", data={"title":"Alien"}).status_code == 403


def test_editor_can_add_movie(client, app):
    owner_id, library_id = create_user(app, "owner")
    editor_id, _ = create_user(app, "editor")
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO library_members (library_id,user_id,role) VALUES (?,?,?)", (library_id, editor_id, "editor"))
        db.commit()
    login(client, "editor")
    response = client.post(f"/libraries/{library_id}/movies/new", data={"title":"Alien", "format":"Blu-ray", "status":"owned"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Alien" in response.data


def test_owner_can_invite_viewer_and_change_role(client, app):
    owner_id, library_id = create_user(app, "owner")
    create_user(app, "friend")
    login(client, "owner")
    response = client.post(f"/libraries/{library_id}/members", data={"username":"friend", "role":"viewer"}, follow_redirects=True)
    assert b"friend" in response.data
    response = client.post(f"/libraries/{library_id}/members/friend/role", data={"role":"editor"}, follow_redirects=True)
    assert b"Editor" in response.data
