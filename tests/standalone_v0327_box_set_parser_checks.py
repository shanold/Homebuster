from pathlib import Path
import importlib.util
import sys

path = Path(__file__).resolve().parents[1] / "movie_catalogue" / "barcode_parser.py"
spec = importlib.util.spec_from_file_location("homebuster_barcode_parser_v0327", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

cases = {
    "Harry Potter 8-Film Collection Blu-ray": "Harry Potter",
    "The Lord of the Rings Trilogy 4K UHD": "The Lord of the Rings",
    "Alien Quadrilogy DVD Box Set": "Alien",
    "Back to the Future Complete Movie Collection Blu-ray": "Back to the Future",
}
for raw, expected in cases.items():
    assert module.detect_movie_box_set_hint(raw), raw
    got = module.movie_box_set_title_candidates(raw)
    assert got and got[0] == expected, (raw, got)

assert module.detect_movie_box_set_hint("Harry Potter Collection Blu-ray")
assert module.movie_box_set_title_candidates("Harry Potter Collection Blu-ray")[0] == "Harry Potter"
assert not module.detect_movie_box_set_hint("The Collection")
assert not module.detect_movie_box_set_hint("The Collection Blu-ray")
assert module.movie_box_set_title_candidates("The Collection")[0] == "The Collection"
print("v0.3.27 movie box-set parser checks passed")
