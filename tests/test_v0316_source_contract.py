from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v0316_source_contract():
    catalog = (ROOT / "movie_catalogue/catalog.py").read_text()
    mobile = (ROOT / "movie_catalogue/mobile_api.py").read_text()
    catalogue = (ROOT / "movie_catalogue/templates/catalogue.html").read_text()
    detail = (ROOT / "movie_catalogue/templates/movie_detail.html").read_text()
    config = (ROOT / "movie_catalogue/config.py").read_text()
    assert "def _group_movie_rows" in catalog
    assert "def _high_confidence_match" in catalog
    assert "match-repair" in catalog
    assert "Match / Repair complete:" in catalog
    assert "_mobile_poster_url(data.get(\"poster_path\"))" in mobile
    assert "Match / Repair Movies" in catalogue
    assert "movie.copy_count > 1" in catalogue
    assert "Physical copies" in detail
    assert 'APP_VERSION = "0.3.16"' in config
