from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys

module_path = Path(__file__).parents[1] / "movie_catalogue" / "barcode_parser.py"
spec = spec_from_file_location("barcode_parser_v0318", module_path)
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

candidates = module.generate_movie_title_candidates
high_confidence = module.high_confidence_tmdb_match

beauty = candidates("Beauty and the beast, DVD and Blu-ray")
assert "Beauty and the beast" in beauty, beauty

bambi = candidates("Bambi Diamond Edition")
assert "Bambi" in bambi, bambi

fievel = candidates("An American Tale(Fievel)")
assert "An American Tale" in fievel, fievel

ace = candidates("Ace Ventura collection")
assert "Ace Ventura" in ace, ace

noisy = candidates("Blah Blah Blah Director's Cut 1987 Action Sony Adventure")
assert "Blah Blah Blah" in noisy, noisy
assert module.infer_legacy_title_year("Blah Blah Blah Director's Cut 1987 Action Sony Adventure") == 1987
assert module.infer_legacy_title_year("Class of 1984") is None

# Minor legacy typo can be accepted when the TMDb candidate is extremely close
# and clearly dominates the alternatives.
choice = high_confidence(
    ["An American Tale"],
    None,
    [
        {"tmdb_id": 1, "title": "An American Tail", "year": 1986},
        {"tmdb_id": 2, "title": "An American Crime", "year": 2007},
    ],
)
assert choice and choice["tmdb_id"] == 1, choice

# A generic collection label must not collapse to one movie just because it is
# the nearest TMDb title.
choice = high_confidence(
    ["Ace Ventura"],
    None,
    [
        {"tmdb_id": 3, "title": "Ace Ventura: Pet Detective", "year": 1994},
        {"tmdb_id": 4, "title": "Ace Ventura: When Nature Calls", "year": 1995},
    ],
)
assert choice is None, choice

# Exact-title remakes stay ambiguous without a year.
choice = high_confidence(
    ["Bambi"],
    None,
    [
        {"tmdb_id": 5, "title": "Bambi", "year": 1942},
        {"tmdb_id": 6, "title": "Bambi", "year": 2025},
    ],
)
assert choice is None, choice

print("v0.3.18 smart legacy-title matching checks passed")
