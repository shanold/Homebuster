from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys

module_path = Path(__file__).parents[1] / "movie_catalogue" / "barcode_parser.py"
spec = spec_from_file_location("barcode_parser_v0319", module_path)
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

infer = module.infer_copy_metadata_from_legacy_title

mixed = infer(
    "Bambi Blu-ray Disney Diamond Edition 2 Disc DVD Kids & Family",
    "Bambi",
)
assert mixed["formats"] == ("Blu-ray", "DVD"), mixed
assert mixed["edition"] == "Diamond Edition", mixed
assert mixed["disc_count"] == 2, mixed

word_disc = infer(
    "Some Movie Blu-ray Prestige Edition two disk Region 1",
    "Some Movie",
)
assert word_disc["formats"] == ("Blu-ray",), word_disc
assert word_disc["edition"] == "Prestige Edition", word_disc
assert word_disc["disc_count"] == 2, word_disc
assert word_disc["region"] == "Region 1", word_disc

language = infer("The English Patient DVD English", "The English Patient")
assert language["language"] == "English", language
assert language["formats"] == ("DVD",), language

protected = infer("Johnny English Blu-ray", "Johnny English")
assert protected["language"] is None, protected
assert protected["formats"] == ("Blu-ray",), protected

combo = infer("Beauty and the Beast, DVD and Blu-ray 2-Disc Platinum Edition", "Beauty and the Beast")
assert combo["formats"] == ("DVD", "Blu-ray"), combo
assert combo["disc_count"] == 2, combo
assert combo["edition"] == "Platinum Edition", combo

print("v0.3.19 canonical metadata repair checks passed")

# Bulk repair is capped at three TMDb searches, so a useful clean title must
# appear within the first three candidates even when one unknown marketing
# word remains between known metadata tokens.
queries = module.generate_movie_title_candidates(
    "Bambi Blu-ray Disney Diamond Edition 2 Disc DVD Kids & Family"
)
assert "Bambi" in queries[:3], queries
queries = module.generate_movie_title_candidates("Beauty and the beast, DVD and Blu-ray")
assert any(module._normalized_title(q) == "beauty and the beast" for q in queries[:3]), queries
queries = module.generate_movie_title_candidates("Some Movie Prestige Edition two disk Blu-ray")
assert any(module._normalized_title(q) == "some movie" for q in queries[:3]), queries
