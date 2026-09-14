from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
db = (ROOT / 'movie_catalogue/db.py').read_text()
libraries = (ROOT / 'movie_catalogue/libraries.py').read_text()
new_html = (ROOT / 'movie_catalogue/templates/library_new.html').read_text()
settings_html = (ROOT / 'movie_catalogue/templates/library_settings.html').read_text()

assert 'default_media_type' in db
assert "DEFAULT 'movie'" in db
assert 'normalize_library_default_media_type' in libraries
assert '{"movie", "tv", "collection"}' in libraries
assert 'name="default_media_type"' in new_html
assert 'name="default_media_type"' in settings_html
print('v0.3.39 library default schema checks passed')
