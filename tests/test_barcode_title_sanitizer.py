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

from movie_catalogue.integrations import parse_barcode_movie_title


def test_extracts_special_edition_format_and_year():
    assert parse_barcode_movie_title("Spider-Man [DVD] Special Edition 2002") == {
        "title": "Spider-Man", "year": 2002, "format": "DVD", "edition": "Special Edition"
    }


def test_extracts_collectors_edition_and_bluray():
    parsed = parse_barcode_movie_title("Alien (Blu-ray) Collector's Edition")
    assert parsed["title"] == "Alien"
    assert parsed["format"] == "Blu-ray"
    assert parsed["edition"] == "Collector's Edition"


def test_extracts_steelbook_4k():
    parsed = parse_barcode_movie_title("Dune 4K UHD SteelBook 2021")
    assert parsed == {"title": "Dune", "year": 2021, "format": "4K UHD", "edition": "SteelBook"}


def test_extracts_combo_formats():
    parsed = parse_barcode_movie_title("The Matrix Blu-ray + DVD Special Edition 1999")
    assert parsed["title"] == "The Matrix"
    assert parsed["year"] == 1999
    assert parsed["format"] == "Blu-ray + DVD"
    assert parsed["edition"] == "Special Edition"


def test_disc_count_can_be_part_of_edition():
    parsed = parse_barcode_movie_title("Blade Runner DVD 2-Disc Special Edition 1982")
    assert parsed["title"] == "Blade Runner"
    assert parsed["format"] == "DVD"
    assert parsed["edition"] == "2-Disc Special Edition"


def test_bracketed_edition_is_extracted():
    parsed = parse_barcode_movie_title("Spider-Man [Special Edition] [DVD] 2002")
    assert parsed == {"title": "Spider-Man", "year": 2002, "format": "DVD", "edition": "Special Edition"}


def test_bracketed_combo_format_is_extracted():
    parsed = parse_barcode_movie_title("Spider-Man [Blu-ray/DVD] Limited Edition 2002")
    assert parsed["title"] == "Spider-Man"
    assert parsed["format"] == "Blu-ray + DVD"
    assert parsed["edition"] == "Limited Edition"
