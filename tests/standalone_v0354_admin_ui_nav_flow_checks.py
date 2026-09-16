from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
tpl=(ROOT/"movie_catalogue/templates/admin_users.html").read_text()
base=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
cfg=(ROOT/"movie_catalogue/config.py").read_text()
assert '>Create User</button>' in tpl
assert '>Add User</button>' not in tpl
assert 'class="card admin-add-user-card"' in tpl
assert '.admin-add-user-card' in css and 'margin-bottom:' in css[css.index('.admin-add-user-card'):css.index('.admin-add-user-card')+150]
# No non-admin placeholder between Libraries and username.
admin_block="{% if current_user.is_admin %}<div class=\"film-cell film-cell-admin\"><a href=\"{{ url_for('admin.users') }}\">Site Admin</a></div>{% endif %}"
assert admin_block in base
assert "{% else %}<div class=\"film-cell film-cell-empty\"" not in base[base.index('film-cell-libraries'):base.index('film-cell-user')]
assert 'APP_VERSION = "0.3.69"' in cfg
print("v0.3.54 admin UI/nav flow checks: PASS")
