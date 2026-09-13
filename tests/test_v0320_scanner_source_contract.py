from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scanner_uses_shared_candidate_generator_and_anchored_metadata():
    text = (ROOT / "movie_catalogue" / "mobile_api.py").read_text()
    assert "generate_movie_title_candidates" in text
    assert "infer_copy_metadata_from_legacy_title" in text
    assert 'product.get("product_title")' in text
    assert '"copy_metadata"' in text


def test_android_saves_selected_match_metadata():
    api = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "homebuster" / "mobile" / "Api.kt").read_text()
    activity = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "homebuster" / "mobile" / "MainActivity.kt").read_text()
    assert "CopyMetadata" in api
    assert "copyMetadata" in api
    assert "match.copyMetadata" in activity


def test_versions_are_v0320():
    config = (ROOT / "movie_catalogue" / "config.py").read_text()
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text()
    assert 'APP_VERSION = "0.3.21"' in config
    assert 'versionName = "0.3.20"' in gradle
    assert "versionCode = 15" in gradle
