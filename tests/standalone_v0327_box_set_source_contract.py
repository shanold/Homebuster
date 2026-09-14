from pathlib import Path
root = Path(__file__).resolve().parents[1]
init = (root / 'movie_catalogue' / '__init__.py').read_text()
db = (root / 'movie_catalogue' / 'db.py').read_text()
integ = (root / 'movie_catalogue' / 'integrations.py').read_text()
mobile = (root / 'movie_catalogue' / 'mobile_api.py').read_text()
box_routes = (root / 'movie_catalogue' / 'box_sets.py').read_text()
service = (root / 'movie_catalogue' / 'box_set_service.py').read_text()
assert 'from .box_sets import bp as box_sets_bp' in init
assert 'app.register_blueprint(box_sets_bp)' in init
assert '/search/collection' in integ
assert 'https://api.themoviedb.org/3/collection/{int(collection_id)}' in integ
assert 'show_box_set_members INTEGER NOT NULL DEFAULT 0' in db
# v0.3.27 legacy tables stay present as migration/rollback source data.
for table in ('box_sets', 'box_set_members', 'box_set_loans', 'box_set_member_loans'):
    assert f'CREATE TABLE IF NOT EXISTS {table}' in db
assert '{"movie", "tv", "collection"}' in mobile
assert 'movie_box_set_title_candidates' in mobile
assert 'tmdb_collection_search' in mobile
assert 'BoxSetLoanConflict' in service
# v0.3.28 intentionally supersedes the v0.3.27 lightweight-member runtime.
assert 'parent_box_set_id' in service
assert 'INSERT INTO movies' in service
assert 'INSERT INTO movies' in box_routes
print('v0.3.27 collection/box-set compatibility checks passed under v0.3.28 member promotion')
