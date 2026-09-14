from pathlib import Path
root=Path(__file__).resolve().parents[1]
config=(root/'movie_catalogue/config.py').read_text()
readme=(root/'README.md').read_text()
assert 'APP_VERSION = "0.3.39"' in config
assert '0.3.39' in readme
assert 'default content type' in readme.lower()
print('v0.3.39 version checks passed')
