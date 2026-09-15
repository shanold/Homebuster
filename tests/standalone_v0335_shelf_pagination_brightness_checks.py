from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
css = (ROOT / 'movie_catalogue/static/styles.css').read_text()
config = (ROOT / 'movie_catalogue/config.py').read_text()

# Both modes need their own client-side pager controls.
for marker in ('shelf-list-pagination', 'shelf-visual-pagination'):
    assert marker in tpl, f'missing {marker}'
assert '50' in tpl and 'LIST_PAGE_SIZE' in tpl, 'list view must page at 50 titles'
assert 'SHELF_ROWS_PER_PAGE' in tpl and re.search(r'SHELF_ROWS_PER_PAGE\s*=\s*4', tpl), 'shelf view must render four rows per page'
assert 'requested * SHELF_ROWS_PER_PAGE' in tpl or 'columns * SHELF_ROWS_PER_PAGE' in tpl, 'shelf page size must follow density x four rows'
assert 'Previous' in tpl and 'Next' in tpl and 'Page ' in tpl, 'pager labels missing'

# Shelf cases are about 50% taller than v0.3.34's 150px desktop height.
m = re.search(r'\.shelf-row\{[^}]*--shelf-case-height:([0-9.]+)px', css)
assert m, 'desktop shelf case height missing'
assert float(m.group(1)) >= 220, f'shelf cases not ~50% taller: {m.group(1)}px'

# Both visual modes should be materially brighter than v0.3.34.
list_opacity = re.search(r'\.shelf-list-card::before\{[^}]*opacity:([0-9.]+)', css)
assert list_opacity and float(list_opacity.group(1)) >= .60, 'list artwork still too dim'
spine = re.search(r'\.shelf-case-spine\{[^}]*background-image:linear-gradient\(90deg,rgba\(8,10,15,([0-9.]+)\)', css)
assert spine and float(spine.group(1)) <= .65, 'shelf spine dark overlay still too strong'

assert any(v in config for v in ('APP_VERSION = "0.3.35"', 'APP_VERSION = "0.3.36"', 'APP_VERSION = "0.3.37"', 'APP_VERSION = "0.3.38"', 'APP_VERSION = "0.3.39"', 'APP_VERSION = "0.3.40"','APP_VERSION = "0.3.41"'))
print('v0.3.35 shelf pagination/brightness checks passed')
