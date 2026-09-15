from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / 'movie_catalogue/static/styles.css').read_text()
config_py = (ROOT / 'movie_catalogue/config.py').read_text()

# The HTML hidden attribute must beat component display rules such as .list-cards{display:flex}.
assert re.search(r'\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important\s*;', css, re.S), \
    'missing global hidden rule that overrides display:flex'

# Shelf list poster art should be brighter than v0.3.33's .34 opacity while preserving the text-side gradient.
m = re.search(r'\.shelf-list-card::before\{[^}]*opacity:([0-9.]+)', css)
assert m, 'shelf list poster opacity not found'
assert float(m.group(1)) >= 0.44, f'poster slice still too dim: opacity={m.group(1)}'

# The far-right overlay should be lighter than the old .88 value so artwork stays visible there.
m2 = re.search(r'\.shelf-list-card::after\{[^}]*background:linear-gradient\(90deg,[^}]*rgba\(25,29,38,([0-9.]+)\) 100%', css)
assert m2, 'shelf list overlay gradient not found'
assert float(m2.group(1)) <= 0.80, f'far-right overlay still too dark: alpha={m2.group(1)}'

assert any(v in config_py for v in ('APP_VERSION = "0.3.34"', 'APP_VERSION = "0.3.35"', 'APP_VERSION = "0.3.36"', 'APP_VERSION = "0.3.37"', 'APP_VERSION = "0.3.38"', 'APP_VERSION = "0.3.39"', 'APP_VERSION = "0.3.40"','APP_VERSION = "0.3.41"'))
print('v0.3.34 shelf hidden/brightness checks passed')
