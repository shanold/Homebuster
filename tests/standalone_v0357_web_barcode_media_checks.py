from pathlib import Path
R=Path(__file__).resolve().parents[1]
nav=(R/'movie_catalogue/templates/_library_nav.html').read_text()
lookup=(R/'movie_catalogue/templates/movie_lookup.html').read_text()
cat=(R/'movie_catalogue/catalog.py').read_text()
mobile=(R/'movie_catalogue/mobile_api.py').read_text()
shared=(R/'movie_catalogue/barcode_matching.py')
config=(R/'movie_catalogue/config.py').read_text()
assert '>Media</a>' in nav and '>Movies</a>' not in nav
assert 'id="barcode-camera-button"' in lookup
assert 'BarcodeDetector' in lookup and 'getUserMedia' in lookup
assert 'name="q"' in lookup and 'Title or barcode' in lookup
assert 'is_barcode_value' in cat and 'barcode_product_lookup' in cat
assert shared.exists()
assert 'from .barcode_matching import barcode_tmdb_matches' in mobile
assert 'def _barcode_tmdb_matches' not in mobile
assert 'barcode' in cat[cat.index('def movie_new_manual'):cat.index('@bp.get("/libraries/<int:library_id>/movies/<int:movie_id>")')]
assert 'APP_VERSION = "0.3.57"' in config
print('v0.3.57 web barcode/media checks: PASS')
