from pathlib import Path
R=Path(__file__).resolve().parents[1]
l=(R/'movie_catalogue/libraries.py').read_text()
t=(R/'movie_catalogue/templates/tv_move_review.html').read_text() if (R/'movie_catalogue/templates/tv_move_review.html').exists() else ''
settings=(R/'movie_catalogue/templates/library_settings.html').read_text()
assert 'def tv_move_review' in l
assert 'def tv_move_apply' in l
assert "media_type='tv'" in l
assert 'selected_movie_ids' in l
assert 'destination_library_id' in l
assert 'INSERT INTO shelves' in l
assert 'UPDATE movies SET library_id=?, shelf_id=?' in l
assert 'TV Move Review' in t
assert 'Select All' in t and 'Select None' in t
assert 'Move Selected' in t
assert 'current shelf' in t.lower()
assert 'Detect &amp; Move TV Shows' in settings
cfg=(R/'movie_catalogue/config.py').read_text();g=(R/'android/app/build.gradle.kts').read_text()
assert 'APP_VERSION = "0.3.73"' in cfg
assert 'versionName = "0.3.41"' in g
assert 'versionCode = 33' in g
print('v0.3.72 TV library move review checks: PASS')
