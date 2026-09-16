from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
config = (ROOT / 'movie_catalogue/config.py').read_text()

assert any(v in config for v in ('APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"', 'APP_VERSION = "0.3.69"')), 'server version not bumped'
for url in (
    'https://upload.wikimedia.org/wikipedia/commons/1/14/Blu-ray_Disc.svg',
    'https://upload.wikimedia.org/wikipedia/commons/e/e7/DVD-Video_Logo.svg',
    'https://upload.wikimedia.org/wikipedia/commons/2/21/Ultra_HD_Blu-ray_%28logo%29.svg',
):
    assert url in tpl, f'missing canonical format logo source: {url}'
assert 'media-logo-image' in tpl
logo_block = tpl.split('const FORMAT_LOGOS = {', 1)[1].split('};', 1)[0]
assert '<svg' not in logo_block.lower(), 'FORMAT_LOGOS still embeds hand-built SVG pseudo-logos'
assert '<text' not in logo_block.lower(), 'FORMAT_LOGOS still draws logo text manually'
print('v0.3.38 canonical format logo checks passed')
