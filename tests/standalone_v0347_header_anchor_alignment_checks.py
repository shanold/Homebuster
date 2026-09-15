from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
css=css[css.index("/* v0.3.47:"):]
assert re.search(r'\.topbar>\.brand\s*\{[^}]*position\s*:\s*absolute[^}]*left\s*:\s*20px',css)
assert re.search(r'\.topbar>\.desktop-nav(?:,\s*\.topbar>\.desktop-nav:not\([^}]+?\))?\s*\{[^}]*position\s*:\s*absolute[^}]*left\s*:\s*50%[^}]*transform\s*:\s*translateX\(-50%\)',css)
assert re.search(r'\.topbar>\.desktop-nav>\*\s*\{[^}]*width\s*:\s*var\(--film-cell\)[^}]*justify-content\s*:\s*center',css)
assert re.search(r'\.topbar::before\s*\{[^}]*background-position-x\s*:\s*0',css)
print("v0.3.47 header anchor/alignment checks: PASS")
