from pathlib import Path
source = Path('movie_catalogue/catalog.py').read_text()
assert 'def _match_queries_for_movie(movie, media_type=None):' in source
# v0.3.28 broadens the override to Movie/TV/Collection, but the key v0.3.26
# guarantee remains: the currently selected type is passed to candidate generation.
assert '_identify_type(media_type or' in source
assert '_match_queries_for_movie(movie, media_type=identify_type)' in source
assert (
    'identify_type = _identify_type(request.args.get("media_type")' in source
    or 'identify_type = _identify_type(explicit_type) if explicit_type else _library_default_type(library)' in source
)
print('v0.3.26 Identify selected-type override source checks passed')
