from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
assert 'class="filmstrip-grid"' in html
assert 'class="desktop-nav filmstrip-nav"' in html
assert re.search(r'\.filmstrip-grid\s*\{[^}]*display\s*:\s*grid[^}]*grid-template-columns\s*:\s*repeat\([^,]+,\s*minmax\(0,\s*1fr\)\)',css)
assert re.search(r'\.filmstrip-nav\s*\{[^}]*display\s*:\s*contents',css)
assert re.search(r'\.filmstrip-nav>\*\s*\{[^}]*justify-content\s*:\s*center[^}]*border-left',css)
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.filmstrip-grid\s*\{[^}]*display\s*:\s*none',css)
print("v0.3.48 responsive filmstrip grid checks: PASS")
