from movie_catalogue.integrations import sanitize_barcode_movie_title


def test_strips_bracketed_dvd_and_extracts_year():
    assert sanitize_barcode_movie_title("Spider-Man [DVD] 2002") == ("Spider-Man", 2002)


def test_strips_parenthesized_bluray():
    assert sanitize_barcode_movie_title("Spider-Man (Blu-ray)") == ("Spider-Man", None)


def test_strips_4k_uhd_qualifier():
    assert sanitize_barcode_movie_title("Spider-Man 4K UHD") == ("Spider-Man", None)


def test_strips_ultra_hd_and_digital_copy():
    assert sanitize_barcode_movie_title("The Matrix Ultra HD + Digital Copy") == ("The Matrix", None)


def test_preserves_normal_movie_title():
    assert sanitize_barcode_movie_title("The DVD") == ("The DVD", None)


def test_normalizes_whitespace():
    assert sanitize_barcode_movie_title("  Spider-Man   [DVD]   ") == ("Spider-Man", None)
