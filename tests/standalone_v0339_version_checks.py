from pathlib import Path
root=Path(__file__).resolve().parents[1]
config=(root/'movie_catalogue/config.py').read_text()
readme=(root/'README.md').read_text()
assert any(v in config for v in ('APP_VERSION = "0.3.68"','APP_VERSION = "0.3.68"','APP_VERSION = "0.3.68"'))
assert '0.3.39' in readme
assert 'default content type' in readme.lower()
print('v0.3.39 version checks passed')
