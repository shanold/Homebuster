import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'movie_catalogue' / 'catalog.py').read_text()
module = ast.parse(source)
node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_find_high_confidence_collection_match')

spec = importlib.util.spec_from_file_location('hb_barcode_parser', ROOT / 'movie_catalogue' / 'barcode_parser.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)

calls = []
def fake_search(title):
    calls.append(title)
    if title == 'Harry Potter':
        return [{'id': 1241, 'title': 'Harry Potter Collection'}]
    return []

ns = {
    'MAX_MATCH_SEARCHES': 3,
    'tmdb_collection_search': fake_search,
    'high_confidence_tmdb_match': parser.high_confidence_tmdb_match,
}
exec(compile(ast.Module(body=[node], type_ignores=[]), '<catalog-helper>', 'exec'), ns)
choice = ns['_find_high_confidence_collection_match'](['Harry Potter'], {})
assert choice and choice['tmdb_id'] == 1241, choice
assert calls == ['Harry Potter'], calls
print('v0.3.31 collection bulk matching behavior passed')
