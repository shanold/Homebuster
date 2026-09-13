from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
cat = (ROOT/'movie_catalogue/catalog.py').read_text()
scan = (ROOT/'movie_catalogue/templates/match_repair.html').read_text()
review = (ROOT/'movie_catalogue/templates/match_repair_review.html').read_text()
config = (ROOT/'movie_catalogue/config.py').read_text()

assert 'APP_VERSION = "0.3.23"' in config
assert 'id="refresh-matched"' in scan and 'name="refresh_matched"' in scan
assert 'refresh_matched' in cat
assert 'tmdb_id IS NULL OR review_pending=1' in cat.replace(' ', ' ')
assert 'search_title' in review
assert 'method="get"' in review and 'name="search_title"' in review
print('PASS v0.3.23 match/repair options contract')
