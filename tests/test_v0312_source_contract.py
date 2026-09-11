from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_barcode_detector_is_separate_from_integrations():
    parser = (ROOT / "movie_catalogue/barcode_parser.py").read_text()
    integrations = (ROOT / "movie_catalogue/integrations.py").read_text()
    assert "def parse_barcode_product_title" in parser
    assert "def rank_tmdb_results" in parser
    assert "parse_barcode_product_title(title, distributor_hint=brand)" in integrations


def test_mobile_api_exposes_and_persists_detected_metadata():
    api = (ROOT / "movie_catalogue/mobile_api.py").read_text()
    for field in ("language", "region", "disc_count", "distributor", "attempts", "best_match"):
        assert field in api
    assert "language,region,disc_count" in api


def test_android_confirmation_can_add_detected_copy():
    main = (ROOT / "android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
    api = (ROOT / "android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
    assert "Homebuster detected" in main
    assert "Catalog/distributor removed from search:" in main
    assert "Add this copy" in main
    assert "api.addMovie(" in main
    assert "val distributor: String?" in api
    assert "val discCount: Int?" in api
