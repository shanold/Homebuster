from pathlib import Path

src = Path('movie_catalogue/db.py').read_text()
assert 'parent_box_set_id INTEGER' in src
assert 'parent_box_set_position INTEGER' in src
assert 'idx_movies_parent_box_set' in src
assert '_migrate_box_set_members_to_movies' in src
assert 'box_set_member_loans' in src and 'INSERT INTO loans' in src
print('v0.3.28 first-class schema source contract passed')
