from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v037_brand_and_mobile_contracts():
    base = (ROOT / "movie_catalogue/templates/base.html").read_text()
    css = (ROOT / "movie_catalogue/static/styles.css").read_text()
    main = (ROOT / "android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
    api = (ROOT / "android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
    assert "brand-icon" in base and "favicon.png" in base
    assert ".brand-icon" in css
    assert "systemBarsPadding()" in main
    assert "data class MovieGroup" in main
    assert "Physical copies" in main
    assert "val version: String?" in api
    assert "val edition: String?" in api

def test_server_version_is_037():
    config = (ROOT / "movie_catalogue/config.py").read_text()
    gradle = (ROOT / "android/app/build.gradle.kts").read_text()
    assert 'APP_VERSION = "0.3.7"' in config
    assert 'versionName = "0.3.7"' in gradle
