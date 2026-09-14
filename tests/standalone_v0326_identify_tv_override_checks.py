from pathlib import Path

source = Path('movie_catalogue/catalog.py').read_text()

assert 'def _match_queries_for_movie(movie, media_type=None):' in source, 'matcher must accept selected media type override'
assert 'media_type = _media_type(media_type or' in source, 'selected media type must override stored row media type'
assert '_match_queries_for_movie(movie, media_type=media_type)' in source, 'Identify route must pass selected media type into matcher'
print('v0.3.26 Identify TV override source checks passed')
