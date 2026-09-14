from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / 'movie_catalogue/catalog.py').read_text()
match_html = (ROOT / 'movie_catalogue/templates/match_repair.html').read_text()
review_html = (ROOT / 'movie_catalogue/templates/match_repair_review.html').read_text()

assert 'def _library_default_type(' in catalog
assert 'library["default_media_type"]' in catalog
assert 'default_search_type=_library_default_type(library)' in catalog
assert 'default_search_type' in match_html
assert "request.args.get(\"media_type\")" in catalog
assert 'stored_media_type = _media_type(movie["media_type"]' in catalog
assert 'media_type=identify_type' in catalog
assert 'name="media_type"' in review_html
print('v0.3.39 web default type checks passed')
