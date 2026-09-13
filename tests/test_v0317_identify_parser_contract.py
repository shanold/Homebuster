from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "movie_catalogue" / "catalog.py"
CONFIG = ROOT / "movie_catalogue" / "config.py"


def test_identify_and_bulk_match_use_barcode_title_parser():
    text = CATALOG.read_text()
    assert "parse_barcode_product_title" in text
    assert "def _match_queries_for_movie" in text
    assert "parsed = parse_barcode_product_title" in text
    assert "query_titles, query_year = _match_queries_for_movie(movie)" in text
    # Both the bulk matcher and the manual Identify page should search with the cleaned query.
    assert text.count("_tmdb_search_candidates(query_titles, query_year)") >= 2
    # Confidence scoring must compare against the same cleaned title/year used for search.
    assert "high_confidence_tmdb_match(query_titles, query_year, normalized)" in text


def test_v0317_server_version():
    assert 'APP_VERSION = "0.3.18"' in CONFIG.read_text()
