import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("barcode_parser", ROOT / "movie_catalogue" / "barcode_parser.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# Scanner candidate generation must clean mixed metadata, not just suffixes.
raw = "Bambi two-disk Diamond Edition Blue-ray DVD Disney Kids & Family"
candidates = module.search_ready_movie_title_candidates(raw)
assert candidates, candidates
assert any(module._normalized_title(c) == "bambi" for c in candidates[:3]), candidates
first = candidates[0].lower()
assert "diamond edition" not in first, candidates[:3]
assert "two-disk" not in first and "two disk" not in first and "blue-ray" not in first, candidates[:3]

# The same anchored metadata inference used by Identify/Repair must recover scanner copy metadata.
metadata = module.infer_copy_metadata_from_legacy_title(raw, "Bambi")
assert metadata["disc_count"] == 2, metadata
assert metadata["edition"].lower() == "diamond edition", metadata
assert "Blu-ray" in metadata["formats"], metadata
assert "DVD" in metadata["formats"], metadata

print("v0.3.20 scanner shared-pipeline parser checks passed")
