from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys

module_path = Path(__file__).parents[1] / "movie_catalogue" / "barcode_parser.py"
spec = spec_from_file_location("barcode_parser_v0317", module_path)
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

parsed = module.parse_barcode_product_title(
    "Blah Blah Blah Director's Cut 1987 Sony Pictures Action & Adventure"
)
assert parsed.title == "Blah Blah Blah", parsed
assert parsed.year == 1987, parsed
assert parsed.edition == "Director's Cut", parsed
assert parsed.distributor == "Sony Pictures", parsed
assert parsed.category == "Action & Adventure", parsed
print("v0.3.17 legacy-title parser check passed")
