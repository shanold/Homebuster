import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

def load_function(path, name, globals_dict=None):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {} if globals_dict is None else dict(globals_dict)
    exec(compile(module, str(path), 'exec'), ns)
    return ns[name]

# Grouping: movie and TV can share numeric TMDb id without colliding.
group = load_function('movie_catalogue/catalog.py', '_group_movie_rows')
rows = [
    {'id': 1, 'tmdb_id': 100, 'media_type': 'movie', 'title': 'Example', 'format': 'DVD', 'poster_path': None, 'active_loan_id': None},
    {'id': 2, 'tmdb_id': 100, 'media_type': 'tv', 'title': 'Example', 'format': 'Blu-ray', 'poster_path': None, 'active_loan_id': None},
    {'id': 3, 'tmdb_id': 100, 'media_type': 'tv', 'title': 'Example', 'format': 'DVD', 'poster_path': None, 'active_loan_id': None},
]
groups = group(rows)
assert len(groups) == 2, groups
assert sorted(g['copy_count'] for g in groups) == [1, 2], groups

# Integration: default makes one movie request; TV makes one TV request with TV year param.
class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {'results': [{'id': 7, 'name': 'Series', 'first_air_date': '2008-01-20', 'poster_path': '/x.jpg'}]}

class FakeRequests:
    def __init__(self): self.calls = []
    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse()

fake_requests = FakeRequests()
current_app = SimpleNamespace(config={'TMDB_API_KEY': 'key'})
tmdb_search = load_function('movie_catalogue/integrations.py', 'tmdb_search', {'current_app': current_app, 'requests': fake_requests})
movie_results = tmdb_search('Bambi')
assert len(fake_requests.calls) == 1 and fake_requests.calls[-1][0].endswith('/search/movie')
assert movie_results == [{'tmdb_id': 7, 'title': '', 'year': None, 'overview': '', 'poster_path': '/x.jpg', 'media_type': 'movie'}]

tv_results = tmdb_search('Breaking Bad', 2008, 'tv')
assert len(fake_requests.calls) == 2 and fake_requests.calls[-1][0].endswith('/search/tv')
assert fake_requests.calls[-1][1]['first_air_date_year'] == 2008
assert tv_results[0]['title'] == 'Series' and tv_results[0]['year'] == 2008 and tv_results[0]['media_type'] == 'tv'
print('v0.3.24 TV behavior checks passed')
