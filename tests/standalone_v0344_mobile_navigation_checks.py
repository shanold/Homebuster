from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/styles.css").read_text()

assert 'class="mobile-menu-toggle"' in html
assert 'id="mobile-site-menu"' in html
assert 'aria-expanded="false"' in html
assert 'aria-controls="mobile-site-menu"' in html
assert '<details' not in html[html.find('<header'):html.find('</header>')+9], "use explicit accessible menu button, not details"
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.desktop-nav\s*\{[^}]*display\s*:\s*none', css)
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.mobile-menu-toggle\s*\{[^}]*display\s*:\s*flex', css)
assert re.search(r'\.desktop-nav\s*\{[^}]*grid-template-columns\s*:\s*repeat\([^;]*var\(--film-cell\)', css)
assert re.search(r'\.topbar>\.brand\s*\{[^}]*grid-column\s*:\s*1\s*/\s*span\s*3', css), "desktop logo reserves film cells"
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.library-nav\s*\{[^}]*overflow-x\s*:\s*auto', css)
print("v0.3.44 mobile navigation checks: PASS")
