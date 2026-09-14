from pathlib import Path
catalog=Path('movie_catalogue/catalog.py').read_text()
box=Path('movie_catalogue/templates/box_set_detail.html').read_text()
detail=Path('movie_catalogue/templates/movie_detail.html').read_text()
api=Path('movie_catalogue/mobile_api.py').read_text()
assert 'm.parent_box_set_id IS NULL' in catalog
assert 'parent_box_set_title' in catalog
assert "url_for('catalog.movie_detail'" in box
assert 'Contained in:' in detail and 'Loaned with box set' in detail
assert 'parent_box_set_id' in api and 'parent_box_set_name' in api
assert 'parent_box_set_title' in catalog and 'parent_box_set_position' in catalog
print('v0.3.28 first-class UI/API contract passed')
