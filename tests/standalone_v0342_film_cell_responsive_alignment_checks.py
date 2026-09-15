from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / "movie_catalogue/static/styles.css").read_text(encoding="utf-8")
html = (ROOT / "movie_catalogue/templates/base.html").read_text(encoding="utf-8")

def require(pattern, message):
    if not re.search(pattern, css, re.S):
        raise AssertionError(message)

assert 'class="topbar-film-grid"' in html, "header needs a shared film grid wrapper"
assert 'film-brand-cell' in html, "brand must occupy explicit film grid cells"
assert 'film-nav-cell' in html, "nav controls must occupy explicit film grid cells"
require(r'\.topbar-film-grid\s*\{[^}]*display\s*:\s*grid', "film grid must use CSS grid")
require(r'\.topbar-film-grid\s*\{[^}]*grid-template-columns\s*:\s*repeat\([^;]*var\(--film-cell\)', "film grid columns must use the same --film-cell as dividers")
require(r'\.film-nav-cell\s*\{[^}]*justify-content\s*:\s*center', "nav cell contents must be horizontally centered")
require(r'@media\s*\(max-width\s*:\s*620px\)[\s\S]*?\.topbar-film-grid\s*\{[^}]*', "mobile must explicitly retain responsive film-grid layout")
print("v0.3.42 responsive film-cell alignment checks: PASS")
