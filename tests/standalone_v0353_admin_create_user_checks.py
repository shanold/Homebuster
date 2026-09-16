from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
admin=(ROOT/"movie_catalogue/admin.py").read_text()
tpl=(ROOT/"movie_catalogue/templates/admin_users.html").read_text()
cfg=(ROOT/"movie_catalogue/config.py").read_text()
assert '@bp.post("/users/create")' in admin
assert 'def create_user' in admin
assert 'USERNAME_RE' in admin
assert 'password_length_error(password, current_app.config' in admin
assert 'generate_password_hash(password)' in admin
assert "INSERT INTO users (username, password_hash, is_admin)" in admin
assert "INSERT INTO libraries (name, owner_id) VALUES ('My Movies', ?)" in admin
assert 'sqlite3.IntegrityError' in admin
assert 'name="is_admin"' in tpl
assert 'action="{{ url_for(\'admin.create_user\') }}"' in tpl
assert 'minlength="{{ password_min_length }}"' in tpl
assert 'APP_VERSION = "0.3.72"' in cfg
print("v0.3.53 admin create-user checks: PASS")
