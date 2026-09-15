from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
css = (ROOT / 'movie_catalogue/static/styles.css').read_text()
config = (ROOT / 'movie_catalogue/config.py').read_text()

assert 'renderFormatBadges' in tpl, 'case preview needs format-logo renderer'
for marker in ('media-logo-dvd', 'media-logo-bluray', 'media-logo-4k'):
    assert marker in tpl, f'missing {marker} vector mark'
assert 'Blu-ray + DVD' in tpl or ('blu-ray' in tpl.lower() and 'dvd' in tpl.lower()), 'combo pack handling missing'
assert 'replaceChildren' in tpl or 'innerHTML' in tpl, 'format band must replace plain text with marks'
assert '.case-preview-logo' in css or '.case-format-logos' in css, 'format-logo container styling missing'
assert '.media-logo-badge' in css, 'format-logo badge styling missing'
assert any(v in config for v in ('APP_VERSION = "0.3.36"','APP_VERSION = "0.3.37"', 'APP_VERSION = "0.3.38"', 'APP_VERSION = "0.3.39"', 'APP_VERSION = "0.3.40"', 'APP_VERSION = "0.3.41"')), 'server version not bumped'
print('v0.3.36 case format logo source checks passed')
