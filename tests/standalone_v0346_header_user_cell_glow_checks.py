from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
assert 'desktop-user-cell' in html
assert re.search(r'\.topbar>\.desktop-nav\s*\{[^}]*grid-column\s*:\s*4\s*/\s*span\s*3',css)
assert re.search(r'\.desktop-user-cell\s*\{[^}]*position\s*:\s*absolute[^}]*right\s*:\s*0[^}]*width\s*:\s*var\(--film-cell\)[^}]*justify-content\s*:\s*center',css)
assert re.search(r'\.brand-wordmark\s*\{[^}]*text-shadow\s*:[^;}]*#(?:ffd|ffe|ffdf|ffe0|ffd7)',css,re.I), "wordmark needs visible yellow edge/glow"
print("v0.3.46 header user-cell/glow checks: PASS")
