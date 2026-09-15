from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
assert re.search(r'/\*\s*v0\.3\.47[\s\S]*?\.topbar>\.brand\s*\{[^}]*position\s*:\s*absolute[^}]*left\s*:\s*20px',css)
assert re.search(r'/\*\s*v0\.3\.47[\s\S]*?\.topbar>\.desktop-nav\s*\{[^}]*grid-column\s*:\s*4\s*/',css)
assert re.search(r'@media\s*\(max-width\s*:\s*760px\)[\s\S]*?\.topbar>\.brand\s*\{[^}]*position\s*:\s*relative',css)
print("v0.3.47 viewport brand anchor checks: PASS")
