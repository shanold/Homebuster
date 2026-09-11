
import ast
from pathlib import Path

PARSER = Path("movie_catalogue/barcode_parser.py")
API = Path("movie_catalogue/mobile_api.py")
ANDROID_API = Path("android/app/src/main/java/com/homebuster/mobile/Api.kt")
ANDROID_MAIN = Path("android/app/src/main/java/com/homebuster/mobile/MainActivity.kt")

def test_parser_source_has_catalog_category_support():
    text = PARSER.read_text()
    assert "_CATALOG_CATEGORY_PATTERN" in text
    assert "category:" in text
    assert '"category": self.category' in text

def test_api_not_found_is_explicit_provider_result():
    text = API.read_text()
    assert '"provider_status": "not_found"' in text
    assert '"UPCitemdb did not find a product for this barcode"' in text

def test_android_shows_upcitemdb_not_found_message():
    api = ANDROID_API.read_text()
    main = ANDROID_MAIN.read_text()
    assert "providerStatus" in api
    assert "UPCitemdb did not find a product for this barcode" in main

def test_android_can_show_removed_category():
    api = ANDROID_API.read_text()
    main = ANDROID_MAIN.read_text()
    assert "val category:" in api
    assert "Category removed from search:" in main
