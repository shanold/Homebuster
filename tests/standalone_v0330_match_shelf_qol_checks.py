from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / 'movie_catalogue' / 'catalog.py').read_text()
MATCH = (ROOT / 'movie_catalogue' / 'templates' / 'match_repair.html').read_text()
SHELVES = (ROOT / 'movie_catalogue' / 'templates' / 'shelves.html').read_text()
CONFIG = (ROOT / 'movie_catalogue' / 'config.py').read_text()
STYLES = (ROOT / 'movie_catalogue' / 'static' / 'styles.css').read_text()

# Match/Repair: automatic high-confidence application remains default-on but can be disabled.
assert 'id="auto-match"' in MATCH, 'Match/Repair has no automatic-match toggle'
assert 'name="auto_match"' in MATCH, 'Automatic-match toggle is not named for the request payload'
assert 'checked' in MATCH.split('id="auto-match"', 1)[1].split('>', 1)[0], 'Automatic matching must default on'
assert 'auto_match' in CATALOG, 'Batch endpoint does not consume the automatic-match setting'
assert 'auto_match: autoMatch.checked' in MATCH, 'Browser does not send automatic-match choice to the batch endpoint'

batch_node = next(n for n in ast.parse(CATALOG).body if isinstance(n, ast.FunctionDef) and n.name == 'match_repair_batch')
batch_source = ast.get_source_segment(CATALOG, batch_node)
assert 'review_pending=1' in batch_source, 'Manual mode does not queue titles for persistent review'
assert 'if not auto_match' in batch_source or 'if auto_match' in batch_source, 'Batch matching has no manual-review branch'

# Shelves: a shelf has its own management view with bulk add/remove flows.
for route_name in ('shelf_detail', 'shelf_add_movies', 'shelf_remove_movies'):
    assert f'def {route_name}(' in CATALOG, f'Missing shelf flow: {route_name}'
assert "url_for('catalog.shelf_detail'" in SHELVES or 'url_for("catalog.shelf_detail"' in SHELVES, 'Shelf list does not open the shelf management screen'

DETAIL_PATH = ROOT / 'movie_catalogue' / 'templates' / 'shelf_detail.html'
assert DETAIL_PATH.exists(), 'Shelf detail template is missing'
DETAIL = DETAIL_PATH.read_text()
assert 'Add movies to shelf' in DETAIL
assert 'Remove movies from shelf' in DETAIL

ADD_PATH = ROOT / 'movie_catalogue' / 'templates' / 'shelf_add_movies.html'
REMOVE_PATH = ROOT / 'movie_catalogue' / 'templates' / 'shelf_remove_movies.html'
assert ADD_PATH.exists(), 'Bulk shelf-add template is missing'
assert REMOVE_PATH.exists(), 'Bulk shelf-remove template is missing'
ADD = ADD_PATH.read_text()
REMOVE = REMOVE_PATH.read_text()
assert 'show_other_shelves' in ADD, 'Add screen has no show-other-shelves toggle'
assert 'Show movies on other shelves' in ADD
# Default must be OFF: only the explicit ?show_other_shelves=1 query enables it.
assert 'request.args.get("show_other_shelves") == "1"' in CATALOG, 'Show-other-shelves is not explicit opt-in'
assert 'movie_ids' in ADD and 'movie_ids' in REMOVE, 'Bulk forms do not submit selected movie IDs'
assert 'Select all visible' in ADD and 'Select all visible' in REMOVE
assert '.bulk-choice' in STYLES, 'Bulk shelf checkbox rows have no dedicated layout styling'

# Query contract: current-shelf movies never appear in Add; default is unshelved only.
add_node = next(n for n in ast.parse(CATALOG).body if isinstance(n, ast.FunctionDef) and n.name == 'shelf_add_movies')
add_source = ast.get_source_segment(CATALOG, add_node)
assert 'shelf_id IS NULL' in add_source, 'Default Add list is not restricted to unshelved movies'
assert 'shelf_id IS NULL OR shelf_id != ?' in add_source or 'shelf_id != ?' in add_source, 'Other-shelf mode does not exclude the current shelf'
assert 'show_other_shelves' in add_source

# Deleting a shelf must explicitly unassign titles (and physical box sets) before deleting it.
delete_node = next(n for n in ast.parse(CATALOG).body if isinstance(n, ast.FunctionDef) and n.name == 'shelf_delete')
delete_source = ast.get_source_segment(CATALOG, delete_node)
assert 'UPDATE movies SET shelf_id=NULL' in delete_source, 'Shelf deletion does not explicitly preserve/unassign movies'
assert 'UPDATE box_sets SET shelf_id=NULL' in delete_source, 'Shelf deletion does not preserve/unassign box sets'
assert 'DELETE FROM movies' not in delete_source, 'Shelf deletion must never delete movies'

# Delete confirmation should explain what happens and include a count.
assert 'will remain in your library' in SHELVES.lower(), 'Shelf delete confirmation does not explain movie preservation'
assert 'movie_count' in SHELVES, 'Shelf delete confirmation does not expose affected count'

assert any(v in CONFIG for v in ('APP_VERSION = "0.3.30"','APP_VERSION = "0.3.31"','APP_VERSION = "0.3.32"','APP_VERSION = "0.3.33"','APP_VERSION = "0.3.34"','APP_VERSION = "0.3.35"', 'APP_VERSION = "0.3.36"', 'APP_VERSION = "0.3.37"', 'APP_VERSION = "0.3.38"'))
print('v0.3.30 Match/Repair + shelf QoL checks passed')
