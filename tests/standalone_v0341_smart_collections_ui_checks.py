from pathlib import Path
cat=Path('movie_catalogue/catalog.py').read_text(); libs=Path('movie_catalogue/libraries.py').read_text(); tpl=Path('movie_catalogue/templates/collections.html').read_text(); settings=Path('movie_catalogue/templates/library_settings.html').read_text(); base=Path('movie_catalogue/templates/base.html').read_text(); css=Path('movie_catalogue/static/styles.css').read_text(); cfg=Path('movie_catalogue/config.py').read_text()
for n in ['smart_collection_approve','smart_collection_dismiss','smart_collection_restore','show_dismissed'] : assert n in cat,n
for n in ['Create Collection','Not interested','Restore suggestion','recommendations may be incomplete','csrf_token'] : assert n in tpl,n
assert 'set_smart_collections' in libs and 'smart_collections_enabled' in libs
assert 'Enable Smart Collections' in settings
assert '<span class="brand-wordmark">HOMEBUSTER</span>' in base
assert '255,214,80' in css.replace(' ','') or '255, 214, 80' in css
assert 'APP_VERSION = "0.3.41"' in cfg
print('v0.3.41 smart collections UI checks passed')

box=Path('movie_catalogue/box_set_service.py').read_text(); assert box.count('ensure_organizational_collection_for_box_set') >= 3
