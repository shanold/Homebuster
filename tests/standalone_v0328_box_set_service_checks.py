from pathlib import Path
src=Path('movie_catalogue/box_set_service.py').read_text()
for text in [
    'parent_box_set_id',
    'INSERT INTO movies',
    'FROM loans l JOIN movies m',
    'convert_movie_to_box_set',
    'reconcile_box_set_members',
]:
    assert text in src, text
assert 'INSERT INTO box_set_member_loans' not in src
print('v0.3.28 first-class box-set service contract passed')
