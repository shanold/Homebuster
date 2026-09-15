from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
shelf = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
catalogue = (ROOT / 'movie_catalogue/templates/catalogue.html').read_text()
catalog_py = (ROOT / 'movie_catalogue/catalog.py').read_text()
config_py = (ROOT / 'movie_catalogue/config.py').read_text()
readme = (ROOT / 'README.md').read_text()

# Shelf view must not depend on localStorage being available.
assert 'const storageGet = ' in shelf
assert 'const storageSet = ' in shelf
assert 'try {' in shelf and 'window.localStorage' in shelf
assert 'storageGet(STORAGE_DENSITY)' in shelf
assert 'storageGet(STORAGE_VIEW)' in shelf
assert 'storageSet(STORAGE_DENSITY' in shelf
assert 'storageSet(STORAGE_VIEW' in shelf
assert shelf.count('localStorage.getItem(') == 1
assert shelf.count('localStorage.setItem(') == 1

# Main library toolbar gets one Export entry instead of two direct CSV links.
assert "url_for('catalog.export_page'" in catalogue
assert '>Export</a>' in catalogue
assert 'Export Movies CSV</a>' not in catalogue
assert 'Export Box Sets CSV</a>' not in catalogue

# Dedicated Export page keeps both existing downloads together.
assert 'def export_page(' in catalog_py
export_template = ROOT / 'movie_catalogue/templates/export.html'
assert export_template.exists()
export_html = export_template.read_text()
assert "url_for('catalog.export_csv'" in export_html
assert "url_for('box_sets.export_csv'" in export_html
assert 'Export Movies CSV' in export_html
assert 'Export Box Sets CSV' in export_html

assert any(v in config_py for v in ('APP_VERSION = "0.3.33"', 'APP_VERSION = "0.3.34"','APP_VERSION = "0.3.35"', 'APP_VERSION = "0.3.36"', 'APP_VERSION = "0.3.37"', 'APP_VERSION = "0.3.38"', 'APP_VERSION = "0.3.39"', 'APP_VERSION = "0.3.40"','APP_VERSION = "0.3.41"'))
assert '## v0.3.33' in readme
print('v0.3.33 shelf toggle/export page checks passed')
