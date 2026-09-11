from movie_catalogue.barcode_parser import parse_barcode_product_title, rank_tmdb_results


def test_detects_language_studio_edition_format_and_year():
    parsed = parse_barcode_product_title(
        "Spider-Man [DVD] English Sony Pictures Home Entertainment Special Edition 2002"
    )
    assert parsed.title == "Spider-Man"
    assert parsed.year == 2002
    assert parsed.formats == ("DVD",)
    assert parsed.language == "English"
    assert parsed.edition == "Special Edition"
    assert parsed.distributor == "Sony Pictures Home Entertainment"


def test_preserves_language_word_when_it_is_part_of_title():
    parsed = parse_barcode_product_title("The English Patient DVD 1996")
    assert parsed.title == "The English Patient"
    assert parsed.language is None
    assert parsed.year == 1996


def test_detects_region_disc_count_and_language():
    parsed = parse_barcode_product_title(
        "Parasite Blu-ray Korean Region A 2-Disc Collector's Edition 2019"
    )
    assert parsed.title == "Parasite"
    assert parsed.formats == ("Blu-ray",)
    assert parsed.language == "Korean"
    assert parsed.region == "Region A"
    assert parsed.disc_count == 2
    assert parsed.edition == "Collector's Edition"
    assert parsed.year == 2019


def test_brand_hint_removes_unknown_distributor_from_suffix():
    parsed = parse_barcode_product_title(
        "Moon DVD English Acme Movie Distribution 2009",
        distributor_hint="Acme Movie Distribution",
    )
    assert parsed.title == "Moon"
    assert parsed.distributor == "Acme Movie Distribution"
    assert parsed.language == "English"


def test_detects_multiple_languages_in_product_metadata():
    parsed = parse_barcode_product_title("Coco Blu-ray English / Spanish Region A 2017")
    assert parsed.title == "Coco"
    assert parsed.language == "English + Spanish"


def test_does_not_strip_studio_from_movie_title():
    parsed = parse_barcode_product_title("Studio 54 DVD 1998")
    assert parsed.title == "Studio 54"
    assert parsed.distributor is None


def test_ranker_prefers_exact_title_and_year():
    results = [
        {"tmdb_id": 2, "title": "Spider-Man 2", "year": 2004},
        {"tmdb_id": 1, "title": "Spider-Man", "year": 2002},
        {"tmdb_id": 3, "title": "Spider-Man", "year": 1977},
    ]
    ranked = rank_tmdb_results("Spider-Man", 2002, results)
    assert ranked[0]["tmdb_id"] == 1
    assert ranked[0]["match_score"] > ranked[1]["match_score"]
