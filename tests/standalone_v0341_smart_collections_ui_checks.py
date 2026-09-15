from pathlib import Path
catalog=Path('movie_catalogue/catalog.py').read_text(); libs=Path('movie_catalogue/libraries.py').read_text(); tpl=Path('movie_catalogue/templates/collections.html').read_text(); settings=Path('movie_catalogue/templates/library_settings.html').read_text(); base=Path('movie_catalogue/templates/base.html').read_text(); css=Path('movie_catalogue/static/styles.css').read_text(); box=Path('movie_catalogue/box_set_service.py').read_text(); config=Path('movie_catalogue/config.py').read_text()
for token in ['smart_collection_approve','smart_collection_dismiss','smart_collection_restore','show_dismissed','backfill_memberships','refresh_collection_cache']: assert token in catalog,token
assert 'set_smart_collections' in libs and 'smart_collections_enabled' in settings
assert 'Show dismissed collections' in tpl and 'Not interested' in tpl and 'Create Collection' in tpl
assert '>HOMEBUSTER<' in base and '255,220,70' in css
assert 'sync_physical_box_set_collection' in box
assert 'APP_VERSION = "0.3.41"' in config
print('v0.3.41 smart collection UI/source checks passed')
