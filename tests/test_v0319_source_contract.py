from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_catalog_imports_canonical_metadata_repair():
    text = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    assert "infer_copy_metadata_from_legacy_title" in text
    assert "def _copy_metadata_fill_values" in text
    assert 'movie["version"]' in text
    assert 'movie["disc_count"]' in text


def test_manual_identify_previews_and_applies_copy_metadata():
    text = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    template = (ROOT / "movie_catalogue" / "templates" / "identify.html").read_text()
    assert "metadata_preview" in text
    assert "_apply_identified_movie" in text
    assert "Detected copy metadata" in template


def test_bulk_repair_is_batched_and_bounded():
    text = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    template = ROOT / "movie_catalogue" / "templates" / "match_repair.html"
    assert '@bp.get("/libraries/<int:library_id>/match-repair")' in text
    assert '@bp.post("/libraries/<int:library_id>/match-repair/batch")' in text
    assert "MAX_MATCH_SEARCHES = 3" in text
    assert "BULK_REPAIR_BATCH_SIZE" in text
    assert "db.commit()" in text
    assert template.exists()
    body = template.read_text()
    assert "processed" in body
    assert "matched" in body
    assert "failed" in body


def test_catalogue_links_to_progress_page_instead_of_long_post():
    text = (ROOT / "movie_catalogue" / "templates" / "catalogue.html").read_text()
    assert "catalog.match_repair_page" in text
    assert "catalog.match_repair_movies" not in text
