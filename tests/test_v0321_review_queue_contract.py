from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_bulk_completion_exposes_review_action_instead_of_dead_complete_button():
    body = (ROOT / "movie_catalogue" / "templates" / "match_repair.html").read_text()
    assert "Review ${totals.unmatched} Movies" in body
    assert "reviewUrl" in body
    assert "button.disabled = true;\n      button.textContent = 'Complete';" not in body


def test_review_queue_route_and_template_exist():
    catalog = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    template = ROOT / "movie_catalogue" / "templates" / "match_repair_review.html"
    assert '@bp.route("/libraries/<int:library_id>/match-repair/review", methods=["GET", "POST"])' in catalog
    assert "def match_repair_review" in catalog
    assert template.exists()


def test_review_queue_can_apply_match_and_skip_to_next_movie():
    catalog = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    body = (ROOT / "movie_catalogue" / "templates" / "match_repair_review.html").read_text()
    assert "_apply_identified_movie" in catalog
    assert "after_id=movie_id" in catalog
    assert "Skip for now" in body
    assert "Use this match" in body
    assert "Still need review" in body


def test_review_queue_is_server_derived_from_unmatched_movies():
    catalog = (ROOT / "movie_catalogue" / "catalog.py").read_text()
    assert "tmdb_id IS NULL" in catalog
    assert "remaining_review" in catalog
