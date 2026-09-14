from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('barcode_parser_v0325', root / 'movie_catalogue' / 'barcode_parser.py')
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

cases = [
    ('Castle Season 1', 'Castle', 'Season 1'),
    ('Castle Complete First Season', 'Castle', 'Complete First Season'),
    ('Castle Complete Series Box Set', 'Castle', 'Complete Series Box Set'),
    ('Castle Box Set', 'Castle', 'Box Set'),
    ('Castle Season 1 Collection', 'Castle', 'Season 1 Collection'),
    ('Castle Season 1 DVD', 'Castle', 'Season 1'),
    ('Castle Complete Series Box Set DVD', 'Castle', 'Complete Series Box Set'),
]

for raw, expected_query, expected_edition in cases:
    candidates = module.search_ready_title_candidates(raw, media_type='tv')
    assert candidates, raw
    assert candidates[0] == expected_query, (raw, candidates)
    metadata = module.infer_copy_metadata_from_legacy_title(raw, 'Castle', media_type='tv')
    assert metadata['edition'] == expected_edition, (raw, metadata)

# Movie mode must not reinterpret TV-set words.
movie_candidates = module.search_ready_title_candidates('Castle Season 1', media_type='movie')
assert movie_candidates[0] != 'Castle', movie_candidates

# A real title ending in a generic word stays untouched unless it matches a set suffix pattern.
assert module.search_ready_title_candidates('The Collection', media_type='tv')[0] == 'The Collection'

print('v0.3.25 TV set parser checks passed')
