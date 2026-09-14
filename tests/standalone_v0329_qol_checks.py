from pathlib import Path
import ast

root = Path(__file__).parents[1]
catalog_path = root / 'movie_catalogue' / 'catalog.py'
identify_template = (root / 'movie_catalogue' / 'templates' / 'identify.html').read_text()
movie_form = (root / 'movie_catalogue' / 'templates' / 'movie_form.html').read_text()
catalog_source = catalog_path.read_text()

# Identify must let the user correct the search title in-place, like Mass Review.
assert 'name="search_title"' in identify_template, 'Identify page has no editable search title field'
identify_node = next(node for node in ast.parse(catalog_source).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'identify_movie')
identify_source = ast.get_source_segment(catalog_source, identify_node)
assert 'request.args.get("search_title")' in identify_source, 'Identify route does not consume an edited search title'
assert 'query_year = None' in identify_source, 'Corrected Identify title is still constrained by stale year metadata'
assert 'search_title=search_title' in identify_source, 'Identify route does not return the edited title to the template'

# Manual physical-copy entry must expose the already-supported normalized combo format.
assert "'Blu-ray + DVD'" in movie_form, 'Manual movie form cannot choose Blu-ray + DVD'


find_node = next(node for node in ast.parse(catalog_source).body if isinstance(node, ast.FunctionDef) and node.name == '_find_high_confidence_match')
find_source = ast.get_source_segment(catalog_source, find_node)
assert '_tmdb_search_with_title_fallback' in find_source, 'Bulk high-confidence matching does not use title-only fallback'

# Execute only the candidate-search helper so Flask is not required in this sandbox.
tree = ast.parse(catalog_source)
funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'_tmdb_search_with_title_fallback', '_tmdb_search_candidates'}]
module = ast.Module(body=funcs, type_ignores=[])
ast.fix_missing_locations(module)

calls = []
def fake_search(title, year=None, media_type='movie'):
    calls.append((title, year, media_type))
    # Simulate bad saved metadata: year-constrained query misses, title-only succeeds.
    if year is not None:
        return []
    return [{'id': 99, 'title': title, 'release_date': '2001-01-01'}]

ns = {'_tmdb_search': fake_search}
exec(compile(module, str(catalog_path), 'exec'), ns)
results = ns['_tmdb_search_candidates'](['Example Movie'], 1997, media_type='movie')
assert results and results[0]['id'] == 99, results
assert calls == [
    ('Example Movie', 1997, 'movie'),
    ('Example Movie', None, 'movie'),
], calls

print('v0.3.29 QoL checks passed')

# The shared barcode parser already understands common combo-pack spellings;
# lock that behavior in for this release so scans normalize to one physical copy.
from importlib.util import spec_from_file_location, module_from_spec
import sys
parser_path = root / 'movie_catalogue' / 'barcode_parser.py'
spec = spec_from_file_location('v0329_barcode_parser', parser_path)
parser = module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)
for raw in [
    'Bambi Diamond Edition Blu-ray DVD',
    'Bambi Diamond Edition Blu-ray + DVD',
    'Bambi Diamond Edition Blu-ray/DVD',
    'Bambi Diamond Edition Blu Ray DVD',
    'Bambi Diamond Edition Blue-ray DVD',
]:
    parsed = parser.parse_barcode_product_title(raw)
    assert parsed.title == 'Bambi', (raw, parsed)
    assert parsed.format == 'Blu-ray + DVD', (raw, parsed)
    assert parsed.edition == 'Diamond Edition', (raw, parsed)
    inferred = parser.infer_copy_metadata_from_legacy_title(raw, 'Bambi')
    assert inferred['format'] == 'Blu-ray + DVD', (raw, inferred)
    assert inferred['edition'] == 'Diamond Edition', (raw, inferred)
