from conftest import create_user, login


def test_admin_can_transfer_private_library_then_delete_user(client, app):
    create_user(app, "admin", admin=True)
    bob_id, bob_library = create_user(app, "bob")
    alice_id, _ = create_user(app, "alice")
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO movies (library_id,title,format,status) VALUES (?,?,?,?)", (bob_library, "Heat", "Blu-ray", "owned"))
        db.commit()
    login(client, "admin")
    response = client.post(
        "/admin/users/bob/delete",
        data={
            "admin_password":"verysecurepass",
            "confirm_username":"bob",
            f"library_action_{bob_library}":f"transfer:{alice_id}",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT 1 FROM users WHERE username='bob'").fetchone() is None
        lib = db.execute("SELECT owner_id FROM libraries WHERE id=?", (bob_library,)).fetchone()
        assert lib["owner_id"] == alice_id
        assert db.execute("SELECT title FROM movies WHERE library_id=?", (bob_library,)).fetchone()["title"] == "Heat"
