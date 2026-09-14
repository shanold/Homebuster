from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / "movie_catalogue/templates/shelf_detail.html").read_text()
css = (ROOT / "movie_catalogue/static/styles.css").read_text()
config_py = (ROOT / "movie_catalogue/config.py").read_text()
readme = (ROOT / "README.md").read_text()

# Shelf page exposes both views and keeps list view as the normal initial view.
assert 'data-shelf-view="list"' in template
assert 'data-shelf-view="shelf"' in template
assert 'id="shelf-list-view"' in template
assert 'id="shelf-visual-view"' in template

# Shelf mode uses poster-derived fake cases/spines rather than pretending we have real spine art.
assert 'class="shelf-case"' in template
assert 'data-poster="{{ movie.poster_path or \'\' }}"' in template
assert 'shelf-case-spine' in template
assert 'shelf-case-title' in template

# Clicking opens a full-poster case preview with the physical format across the top.
assert 'id="shelf-case-modal"' in template
assert 'id="case-preview-poster"' in template
assert 'id="case-preview-format"' in template
assert 'Open details' in template

# Density changes live and is remembered locally. View mode is remembered too.
assert 'id="shelf-density"' in template
assert 'Homebuster.shelfViewMode' in template
assert 'Homebuster.shelfDensity' in template
assert "style.setProperty('--shelf-columns'" in template
assert "addEventListener('input'" in template

# List view receives subtle poster slices without replacing the readable foreground content.
assert 'shelf-list-card' in template
assert '--shelf-list-poster' in template
assert '.shelf-list-card::before' in css
assert '.shelf-list-card::after' in css

# Visual shelf/case/modal styling exists and has a responsive density fallback.
for selector in ['.visual-shelf', '.shelf-row', '.shelf-case', '.shelf-case-spine', '.case-preview-dialog', '.case-preview-logo']:
    assert selector in css, selector
assert '--shelf-columns' in css
assert '@media(max-width:620px)' in css

assert any(v in config_py for v in ('APP_VERSION = "0.3.32"', 'APP_VERSION = "0.3.33"', 'APP_VERSION = "0.3.34"','APP_VERSION = "0.3.35"', 'APP_VERSION = "0.3.36"', 'APP_VERSION = "0.3.37"'))
assert '## v0.3.32' in readme
print('v0.3.32 shelf view checks passed')
