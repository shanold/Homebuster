from pathlib import Path
s=Path('movie_catalogue/db.py').read_text()
for token in ['smart_collections_enabled','tmdb_collection_id','tmdb_collection_name','tmdb_last_refreshed_at','tmdb_movie_collection_cache','smart_collection_dismissals','idx_collections_library_tmdb_unique']:
    assert token in s, token
print('v0.3.41 smart collection schema source checks passed')
