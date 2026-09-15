from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
header=(ROOT/"movie_catalogue/static/header.css")
assert header.exists(), "dedicated header stylesheet missing"
hc=header.read_text()
assert "header.css" in html
assert html.index("styles.css") < html.index("header.css"), "header.css must load after legacy stylesheet"
assert re.search(r'\.topbar\s+\.desktop-filmstrip\s*\{[^}]*display\s*:\s*grid',hc)
assert re.search(r'\.topbar\s+\.desktop-filmstrip\s*>\s*\.film-cell\s*\{[^}]*display\s*:\s*flex',hc)
assert re.search(r'\.topbar\s+\.desktop-filmstrip\s*>\s*\.film-cell\s*>\s*\*\s*\{[^}]*width\s*:\s*100%[^}]*min-width\s*:\s*0',hc)
assert re.search(r'@media\s*\(max-width:\s*760px\)[\s\S]*?\.topbar\s+\.desktop-filmstrip\s*\{[^}]*display\s*:\s*none',hc)
assert "--film-cell" not in hc, "new desktop header must not use fixed film-cell widths"
print("v0.3.51 header CSS isolation checks: PASS")
