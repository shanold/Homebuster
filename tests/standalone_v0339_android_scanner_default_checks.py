from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / 'android/app/src/main/java/com/homebuster/mobile/Api.kt').read_text()
main = (ROOT / 'android/app/src/main/java/com/homebuster/mobile/MainActivity.kt').read_text()
server = (ROOT / 'movie_catalogue/mobile_api.py').read_text()

assert 'data class Library' in api
assert '@SerializedName("default_media_type")' in api
assert 'val defaultMediaType: String = "movie"' in api
assert 'data class LibrariesResponse' in api
assert 'suspend fun libraries(' in api
assert '@SerializedName("library_id") val libraryId: Int?' in api
assert 'fun barcode(' in api and '@Query("library_id")' in api
assert 'addBoxSet' in api
assert 'activeLibrary' in main
assert 'initialMediaType' in main
assert 'mediaType = "collection"' in main
assert 'defaultMediaType' in main
assert 'request.args.get("library_id", type=int)' in server
assert '"tmdb_id": item.get("id")' in server
assert '"media_type": "collection"' in server
print('v0.3.39 Android scanner default checks passed')
