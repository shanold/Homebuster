from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
assert 'id="mobile-site-menu"' in html
assert 'Signed in as' in html
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.topbar>\.mobile-site-menu\s*\{[^}]*display\s*:\s*flex[^}]*flex-direction\s*:\s*column',css)
assert re.search(r'\.topbar>\.mobile-site-menu>\*\s*\{[^}]*width\s*:\s*100%[^}]*min-width\s*:\s*0',css)
assert re.search(r'\.topbar>\.mobile-site-menu\s*\{[^}]*right\s*:\s*10px[^}]*width\s*:\s*min\(240px',css)
print("v0.3.45 mobile menu layout checks: PASS")
