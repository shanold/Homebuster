from pathlib import Path
s=Path('movie_catalogue/db.py').read_text()
for needle in ['smart_collections_enabled INTEGER NOT NULL DEFAULT 1','tmdb_collection_id INTEGER','tmdb_collection_name TEXT','tmdb_last_refreshed_at TEXT','tmdb_movie_collection_cache','smart_collection_dismissals','smart_collection_parts','smart_collection_refresh_state','idx_collections_library_tmdb_unique','WHERE tmdb_collection_id IS NOT NULL']:
    assert needle in s, needle
print('v0.3.41 smart collections schema checks passed')
