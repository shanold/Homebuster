from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
cfg=(ROOT/"movie_catalogue/config.py").read_text()
assert 'APP_VERSION = "0.3.65"' in cfg
m=re.search(r"url_for\('static',\s*filename='styles\.css'[^)]*\)",html)
assert m, "main stylesheet url_for missing"
assert re.search(r"(?:v|version)\s*=\s*config\['APP_VERSION'\]",m.group(0)), "stylesheet is not version cache-busted"
print("v0.3.50 static cache busting checks: PASS")
