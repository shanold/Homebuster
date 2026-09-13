from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_review_queue_is_persistent_and_library_visible():
    db = read('movie_catalogue/db.py')
    catalog = read('movie_catalogue/catalog.py')
    tpl = read('movie_catalogue/templates/catalogue.html')
    review = read('movie_catalogue/templates/match_repair_review.html')
    assert 'review_pending INTEGER NOT NULL DEFAULT 0' in db
    assert 'ALTER TABLE movies ADD COLUMN review_pending INTEGER NOT NULL DEFAULT 0' in db
    assert 'SET review_pending=1' in catalog
    assert 'review_pending=1' in catalog
    assert 'pending_review_count' in catalog
    assert 'Review unmatched movies' in tpl
    assert 'Dismiss from review' in review
    assert 'review_pending=0' in catalog

if __name__ == '__main__':
    test_review_queue_is_persistent_and_library_visible()
    print('PASS v0.3.22 review queue contract')
