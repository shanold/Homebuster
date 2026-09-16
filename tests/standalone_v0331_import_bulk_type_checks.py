from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / 'movie_catalogue' / 'catalog.py').read_text()
BOXSETS = (ROOT / 'movie_catalogue' / 'box_sets.py').read_text()
HOME = (ROOT / 'movie_catalogue' / 'templates' / 'catalogue.html').read_text()
MATCH = (ROOT / 'movie_catalogue' / 'templates' / 'match_repair.html').read_text()
CONFIG = (ROOT / 'movie_catalogue' / 'config.py').read_text()

# Main library toolbar is decluttered: imports live behind one Import page.
assert "url_for('catalog.import_page'" in HOME
assert 'Import Movies CSV' not in HOME
assert 'Import Box Sets CSV' not in HOME
assert '@bp.get("/libraries/<int:library_id>/import")' in CATALOG
assert 'render_template("import.html"' in CATALOG
IMPORT = (ROOT / 'movie_catalogue' / 'templates' / 'import.html').read_text()
assert 'Import Movies CSV' in IMPORT
assert 'Import Box Sets CSV' in IMPORT
assert "url_for('catalog.import_csv'" in IMPORT
assert "url_for('box_sets.import_csv'" in IMPORT

# Bulk repair explicitly selects exactly one TMDb endpoint.
assert 'id="search-type"' in MATCH
assert 'Movie Collection / Box Set' in MATCH
assert 'TV / Box Set' in MATCH
assert 'search_type:' in MATCH
assert 'media_type=${encodeURIComponent(searchType.value)}' in MATCH
assert 'bulk_search_type = _identify_type(payload.get("search_type")' in CATALOG
assert '_find_high_confidence_collection_match' in CATALOG
assert 'tmdb_collection_details' in CATALOG
assert '_convert_identified_movie_to_collection' in CATALOG
assert 'media_type=identify_type' in CATALOG

# Existing matched rows keep their stored type when refresh_matched is enabled.
assert 'if tmdb_id:' in CATALOG
assert (
    'media_type = _media_type(movie["media_type"]' in CATALOG
    or 'stored_media_type = _media_type(movie["media_type"]' in CATALOG
)

assert any(v in CONFIG for v in ('APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"','APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"'))
print('v0.3.31 import hub + bulk TMDb type checks passed')
