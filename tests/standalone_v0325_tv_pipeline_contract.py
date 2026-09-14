from pathlib import Path
root=Path(__file__).resolve().parents[1]
cat=(root/'movie_catalogue/catalog.py').read_text()
mobile=(root/'movie_catalogue/mobile_api.py').read_text()
parser=(root/'movie_catalogue/barcode_parser.py').read_text()

def need(ok,msg):
    if not ok: raise AssertionError(msg)

need('search_ready_title_candidates' in cat, 'catalog does not use TV-aware candidates')
need('search_ready_title_candidates' in mobile, 'mobile scanner does not use TV-aware candidates')
need('media_type=media_type' in mobile.split('infer_copy_metadata_from_legacy_title',1)[1], 'mobile metadata inference is not media-aware')
need('media_type=media_type' in cat.split('infer_copy_metadata_from_legacy_title',1)[1], 'catalog metadata inference is not media-aware')
need('def search_ready_title_candidates' in parser, 'shared TV-aware search candidate function missing')
print('v0.3.25 TV pipeline source contract checks passed')
