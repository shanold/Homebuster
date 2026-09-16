from pathlib import Path
root=Path(__file__).resolve().parents[1]
t=(root/'movie_catalogue/templates/shelf_detail.html').read_text()
c=(root/'movie_catalogue/static/styles.css').read_text()
config=(root/'movie_catalogue/config.py').read_text()
for token in ['case-preview-plastic','case-preview-insert','data-case-format','case-style-bluray','case-style-dvd','case-style-uhd']:
    assert token in t or token in c, f'missing physical case token {token}'
assert 'case-format-band case-format-logos' not in t, 'old banner-style format strip still present'
assert any(v in config for v in ('APP_VERSION = "0.3.71"', 'APP_VERSION = "0.3.71"', 'APP_VERSION = "0.3.71"', 'APP_VERSION = "0.3.71"', 'APP_VERSION = "0.3.71"')), 'server version not bumped'
print('v0.3.37 physical case preview source checks passed')
