from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys

module_path = Path(__file__).parents[1] / 'movie_catalogue' / 'barcode_parser.py'
spec = spec_from_file_location('barcode_parser_under_test', module_path)
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
parse = module.parse_barcode_product_title
rank = module.rank_tmdb_results

cases = [
    ("Spider-Man [DVD] English Sony Pictures Home Entertainment Special Edition 2002", {
        'title':'Spider-Man','year':2002,'formats':('DVD',),'language':'English','edition':'Special Edition','distributor':'Sony Pictures Home Entertainment'
    }),
    ("The English Patient DVD 1996", {'title':'The English Patient','year':1996,'language':None}),
    ("Parasite Blu-ray Korean Region A 2-Disc Collector's Edition 2019", {
        'title':'Parasite','formats':('Blu-ray',),'language':'Korean','region':'Region A','disc_count':2,'edition':"Collector's Edition",'year':2019
    }),
    ("Coco Blu-ray English / Spanish Region A 2017", {'title':'Coco','language':'English + Spanish'}),
    ("Studio 54 DVD 1998", {'title':'Studio 54','distributor':None}),
]
for raw, expected in cases:
    result = parse(raw)
    for field, value in expected.items():
        actual = getattr(result, field)
        assert actual == value, (raw, field, actual, value, result)

brand = parse("Moon DVD English Acme Movie Distribution 2009", distributor_hint="Acme Movie Distribution")
assert brand.title == 'Moon'
assert brand.distributor == 'Acme Movie Distribution'
assert brand.language == 'English'

ranked = rank('Spider-Man', 2002, [
    {'tmdb_id':2,'title':'Spider-Man 2','year':2004},
    {'tmdb_id':1,'title':'Spider-Man','year':2002},
    {'tmdb_id':3,'title':'Spider-Man','year':1977},
])
assert ranked[0]['tmdb_id'] == 1, ranked
assert ranked[0]['match_score'] > ranked[1]['match_score'], ranked
print('standalone barcode parser checks passed')
combo = parse("Spider-Man [Blu-ray/DVD] Limited Edition 2002")
assert combo.title == "Spider-Man", combo
assert combo.formats == ("Blu-ray", "DVD"), combo
assert combo.edition == "Limited Edition", combo
combo2 = parse("The Matrix Blu-ray + DVD Special Edition 1999")
assert combo2.formats == ("Blu-ray", "DVD"), combo2
assert combo2.title == "The Matrix", combo2
johnny = parse("Johnny English DVD 2003")
assert johnny.title == "Johnny English", johnny
assert johnny.language is None, johnny
labeled = parse("Amelie Blu-ray Language: French 2001")
assert labeled.title == "Amelie", labeled
assert labeled.language == "French", labeled
english_vinglish = parse("English Vinglish DVD 2012")
assert english_vinglish.title == "English Vinglish", english_vinglish
assert english_vinglish.language is None, english_vinglish
metadata_language = parse("Spider-Man DVD English 2002")
assert metadata_language.title == "Spider-Man", metadata_language
assert metadata_language.language == "English", metadata_language
region = parse("The Matrix DVD NTSC Region 1 1999")
assert region.title == "The Matrix", region
assert region.region == "Region 1", region
