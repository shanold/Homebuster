from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / 'movie_catalogue/templates/shelf_add_movies.html').read_text()
base = (ROOT / 'movie_catalogue/templates/base.html').read_text()
css = (ROOT / 'movie_catalogue/static/styles.css').read_text()

# Checking the filter must immediately re-run the GET filter instead of requiring
# the user to discover/click a separate Apply button.
assert 'name="show_other_shelves"' in template
assert 'data-show-other-shelves' in template
assert 'requestSubmit()' in template

# Keep the brand icon but style the Homebuster word separately.
assert 'class="brand-wordmark"' in base
assert '.brand-wordmark' in css
assert 'Impact' in css or 'Arial Black' in css
assert '#b' in css.lower() or 'purple' in css.lower()
print('v0.3.40 shelf toggle and branding source checks passed')
