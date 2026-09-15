from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/header.css").read_text()
assert html.count('class="film-cell film-cell-empty"') == 9, "source contains 8 decorative cells plus non-admin end compensation"
assert 'class="film-cell film-cell-libraries"' in html
assert 'class="film-cell film-cell-admin"' in html
assert 'class="film-cell film-cell-user"' in html
assert 'class="film-cell film-cell-logout"' in html
assert re.search(r'\.topbar \.desktop-filmstrip>\.film-cell\s*\{[^}]*border-left',css)
assert 'nth-of-type' not in css, "cell placement must come from DOM flow, not positional CSS"
assert re.search(r'\.film-cell-empty\s*\{[^}]*pointer-events\s*:\s*none',css)
print("v0.3.52 full film-cell strip checks: PASS")
