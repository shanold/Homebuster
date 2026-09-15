from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
css=(ROOT/"movie_catalogue/static/styles.css").read_text()
asset=ROOT/"movie_catalogue/static/homebuster-wordmark.png"
assert asset.exists(), "transparent wordmark asset missing"
assert 'homebuster-wordmark.png' in html
assert 'class="brand-wordmark-image"' in html
assert '<span class="brand-wordmark">HOMEBUSTER</span>' not in html
assert '.brand-wordmark-image' in css
print("v0.3.46 branded wordmark image checks: PASS")
