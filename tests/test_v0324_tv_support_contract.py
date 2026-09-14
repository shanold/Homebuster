from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_database_persists_media_type():
    db = read('movie_catalogue/db.py')
    assert "media_type TEXT NOT NULL DEFAULT 'movie'" in db
    assert 'ALTER TABLE movies ADD COLUMN media_type' in db


def test_tmdb_integration_supports_explicit_tv_mode():
    integrations = read('movie_catalogue/integrations.py')
    assert 'def tmdb_search(query: str, year: int | None = None, media_type: str = "movie")' in integrations
    assert 'endpoint = "tv" if media_type == "tv" else "movie"' in integrations and 'search/{endpoint}' in integrations


def test_web_matching_and_grouping_are_media_type_aware():
    catalog = read('movie_catalogue/catalog.py')
    assert '(movie.get("media_type") or "movie", movie.get("tmdb_id"))' in catalog
    assert 'media_type=media_type' in catalog
    assert 'request.values.get("media_type")' in catalog or 'request.args.get("media_type")' in catalog


def test_android_api_carries_media_type_and_explicit_tmdb_mode():
    api = read('android/app/src/main/java/com/homebuster/mobile/Api.kt')
    main = read('android/app/src/main/java/com/homebuster/mobile/MainActivity.kt')
    assert '@SerializedName("media_type") val mediaType: String = "movie"' in api
    assert '@Query("media_type") mediaType: String = "movie"' in api
    assert '@SerializedName("media_type") val mediaType: String = "movie"' in api
    assert 'mediaType' in main and 'TV' in main and 'Movie' in main


def test_version_bumped_for_server_and_android():
    config = read('movie_catalogue/config.py')
    gradle = read('android/app/build.gradle.kts')
    assert any(v in config for v in ('0.3.24','0.3.25','0.3.26','0.3.27','0.3.28'))
    assert 'versionName = "0.3.24"' in gradle or 'versionName = "0.3.25"' in gradle
