from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / 'movie_catalogue/mobile_api.py').read_text()

assert 'default_media_type' in api
assert 'SELECT l.id, l.name, l.default_media_type' in api
assert 'request.args.get("media_type")' in api
print('v0.3.39 mobile library default checks passed')
