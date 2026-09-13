from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_v0318_catalog_uses_multi_candidate_legacy_matching():
    text = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    assert "generate_movie_title_candidates" in text
    assert "infer_legacy_title_year" in text
    assert "high_confidence_tmdb_match" in text
    assert "def _match_queries_for_movie" in text
    assert "else infer_legacy_title_year(raw_title)" in text
    assert "def _tmdb_search_candidates" in text
    assert "_tmdb_search_candidates(query_titles, query_year)" in text
    assert "high_confidence_tmdb_match(query_titles, query_year, normalized)" in text


def test_v0318_server_version_and_android_stays_release_compatible():
    config = (ROOT / "movie_catalogue" / "config.py").read_text()
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text()
    assert 'APP_VERSION = "0.3.18"' in config
    assert 'versionName = "0.3.16"' in gradle
    assert 'versionCode = 14' in gradle
