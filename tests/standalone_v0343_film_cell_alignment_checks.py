from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/'movie_catalogue/static/styles.css').read_text()
html=(ROOT/'movie_catalogue/templates/base.html').read_text()
assert 'topbar-film-grid' not in html
assert '<a class="brand"' in html
assert re.search(r'\.topbar\s*\{[^}]*grid-template-columns\s*:\s*repeat\(auto-fit,var\(--film-cell\)\)', css, re.S)
assert re.search(r'\.topbar>nav\s*\{[^}]*grid-column\s*:\s*span 4 / -1', css, re.S), 'admin nav must end on an actual film grid line'
assert re.search(r'\.topbar>nav:not\(:has\(>:nth-child\(4\)\)\)\s*\{[^}]*grid-column\s*:\s*span 3 / -1', css, re.S), 'three-control nav must also end on a film grid line'
assert re.search(r'\.topbar nav>\*\s*\{[^}]*width\s*:\s*var\(--film-cell\)', css, re.S)
assert re.search(r'@media\(max-width:620px\)[\s\S]*?\.topbar>nav,[\s\S]*?\{[^}]*grid-column\s*:\s*1 / -1', css, re.S), 'phone nav must start from the left-origin film grid on its own row'
assert re.search(r'@media\(max-width:620px\)[\s\S]*?\.topbar>\.brand\s*\{[^}]*grid-row\s*:\s*1', css, re.S), 'brand stays left on first mobile row'
print('v0.3.43 film-cell alignment checks: PASS')
