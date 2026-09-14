from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(path): return (ROOT / path).read_text(encoding='utf-8')
checks = []
def need(cond, msg):
    if not cond: raise AssertionError(msg)

db = read('movie_catalogue/db.py')
need("media_type TEXT NOT NULL DEFAULT 'movie'" in db, 'database schema missing media_type')
need('ALTER TABLE movies ADD COLUMN media_type' in db, 'migration missing media_type')

integrations = read('movie_catalogue/integrations.py')
need('media_type: str = "movie"' in integrations, 'tmdb search missing media type')
need('endpoint = "tv" if media_type == "tv" else "movie"' in integrations and 'search/{endpoint}' in integrations, 'tmdb TV endpoint missing')

catalog = read('movie_catalogue/catalog.py')
need('(movie.get("media_type") or "movie", movie.get("tmdb_id"))' in catalog, 'grouping not media-aware')
need('media_type=media_type' in catalog, 'web TMDb calls not media-aware')

api = read('android/app/src/main/java/com/homebuster/mobile/Api.kt')
main = read('android/app/src/main/java/com/homebuster/mobile/MainActivity.kt')
need('@SerializedName("media_type") val mediaType: String = "movie"' in api, 'Android models missing media_type')
need('@Query("media_type") mediaType: String = "movie"' in api, 'Android TMDb endpoint missing media_type query')
need('TV' in main and 'Movie' in main and 'mediaType' in main, 'Android UI missing media type control')

config = read('movie_catalogue/config.py')
gradle = read('android/app/build.gradle.kts')
need(any(v in config for v in ('0.3.24','0.3.25','0.3.26','0.3.27','0.3.28','0.3.29','0.3.30','0.3.31','0.3.32','0.3.33','0.3.34','0.3.35','0.3.36','0.3.37','0.3.38')), 'server TV-support version missing')
need('versionName = "0.3.24"' in gradle or 'versionName = "0.3.25"' in gradle, 'Android TV-support version missing')
print('v0.3.24 TV support source contract checks passed')
