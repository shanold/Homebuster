from pathlib import Path
catalog=Path('movie_catalogue/catalog.py').read_text()
identify=Path('movie_catalogue/templates/identify.html').read_text()
review=Path('movie_catalogue/templates/match_repair_review.html').read_text()
assert 'def _identify_type' in catalog
assert 'movie_box_set_title_candidates' in catalog
assert 'tmdb_collection_search' in catalog and 'tmdb_collection_details' in catalog
assert '_convert_identified_movie_to_collection' in catalog
assert 'media_type="collection"' in catalog or 'media_type=\"collection\"' in catalog
for text in (identify, review):
    assert 'value="collection"' in text
    assert 'Movie Collection / Box Set' in text
assert 'parent_box_set_id IS NULL' in catalog
print('v0.3.28 collection identify/review contract passed')
