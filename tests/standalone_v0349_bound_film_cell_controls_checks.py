from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
for name in ("Libraries","Site Admin","Log out"):
    assert re.search(r'class="film-cell[^"]*"[^>]*>[\s\S]{0,500}?'+re.escape(name),html), f"{name} not inside a film cell"
assert 'class="film-cell film-cell-user"' in html
assert re.search(r'\.desktop-filmstrip\s*\{[^}]*display\s*:\s*grid[^}]*grid-template-columns\s*:\s*repeat\(12,\s*minmax\(0,\s*1fr\)\)',css)
assert re.search(r'\.desktop-filmstrip>\.film-cell\s*\{[^}]*display\s*:\s*flex[^}]*justify-content\s*:\s*center',css)
assert re.search(r'\.desktop-filmstrip>\.film-cell>\*\s*\{[^}]*width\s*:\s*100%[^}]*height\s*:\s*100%',css)
print("v0.3.49 bound film-cell controls checks: PASS")
