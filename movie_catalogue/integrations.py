from __future__ import annotations

import re
from datetime import datetime
import requests
from flask import current_app

_MEDIA_TOKEN = r"(?:DVD|Blu[- ]?ray|4K(?:\s+UHD)?|UHD|Ultra\s+HD|Digital\s+Copy|Combo\s+Pack)"
_MEDIA_SEQUENCE = rf"{_MEDIA_TOKEN}(?:\s*(?:\+|/|&)\s*{_MEDIA_TOKEN})*"
_BRACKETED_MEDIA_RE = re.compile(rf"\s*[\[(]\s*{_MEDIA_SEQUENCE}\s*[\])]\s*", re.I)
_TRAILING_MEDIA_RE = re.compile(
    rf"(?:\s*[-–:+]\s*|\s+)(?:{_MEDIA_TOKEN})(?:\s*(?:\+|/|&)\s*(?:{_MEDIA_TOKEN}))*\s*$",
    re.I,
)
_TRAILING_YEAR_RE = re.compile(r"(?:\s*[\[(]?\s*)((?:19|20)\d{2})(?:\s*[\])])?\s*$")

_EDITION_NAMES = (
    r"Special(?:\s+Collector'?s?)?\s+Edition|Collector'?s?\s+Edition|Limited\s+Edition|"
    r"Anniversary\s+Edition|Deluxe\s+Edition|Ultimate\s+Edition|Platinum\s+Edition|"
    r"Diamond\s+Edition|Signature\s+Collection|Criterion\s+Collection|"
    r"Extended(?:\s+(?:Edition|Cut))?|Director'?s\s+Cut|Theatrical\s+Cut|Final\s+Cut|"
    r"Unrated(?:\s+Edition)?|Uncut(?:\s+Edition)?|Remastered(?:\s+Edition)?|"
    r"Restored(?:\s+Edition)?|SteelBook|Widescreen|Full\s+Screen"
)
_EDITION_SUFFIX_RE = re.compile(
    rf"(?:\s*[-–:+]\s*|\s+)(?P<edition>(?:(?:\d+)[- ]Disc\s+)?(?:{_EDITION_NAMES}))\s*$",
    re.I,
)
_DISC_SUFFIX_RE = re.compile(r"(?:\s*[-–:+]\s*|\s+)(?P<edition>\d+[- ]Disc(?:\s+Set)?)\s*$", re.I)
_BRACKETED_EDITION_RE = re.compile(rf"\s*[\[(]\s*(?P<edition>(?:(?:\d+)[- ]Disc\s+)?(?:{_EDITION_NAMES}))\s*[\])]\s*", re.I)


def _canonical_format(token: str) -> str | None:
    value = re.sub(r"\s+", " ", token.strip()).lower().replace("-", " ")
    if "4k" in value or value == "uhd" or "ultra hd" in value:
        return "4K UHD"
    if "blu" in value and "ray" in value:
        return "Blu-ray"
    if value == "dvd":
        return "DVD"
    return None


def parse_barcode_movie_title(raw_title: str) -> dict:
    """Split barcode-provider product text into movie search metadata.

    Raw text is never modified outside this return value.  The parser is
    deliberately suffix/bracket oriented so ordinary words inside a title are
    less likely to be mistaken for packaging metadata.
    """
    original = re.sub(r"\s+", " ", (raw_title or "").strip())
    if not original:
        return {"title": "", "year": None, "format": None, "edition": None}

    title = original
    year = None
    formats: list[str] = []
    editions: list[str] = []

    def strip_trailing_year(value: str) -> str:
        nonlocal year
        match = _TRAILING_YEAR_RE.search(value)
        if match:
            candidate = int(match.group(1))
            if 1900 <= candidate <= datetime.now().year + 1:
                year = candidate
                return value[:match.start()].strip()
        return value

    title = strip_trailing_year(title)

    # Capture media tokens before removing them.
    for match in re.finditer(_MEDIA_TOKEN, title, re.I):
        canonical = _canonical_format(match.group(0))
        if canonical and canonical not in formats:
            formats.append(canonical)

    for match in _BRACKETED_EDITION_RE.finditer(title):
        edition = re.sub(r"\s+", " ", match.group("edition")).strip()
        if edition and edition not in editions:
            editions.append(edition)
    title = _BRACKETED_EDITION_RE.sub(" ", title).strip()

    # Remove only trailing/bracketed packaging metadata, repeating because
    # stores frequently order it differently (e.g. "2002 Special Edition DVD").
    previous = None
    while title != previous:
        previous = title
        title = strip_trailing_year(title)
        title = _BRACKETED_MEDIA_RE.sub(" ", title).strip()
        title = _TRAILING_MEDIA_RE.sub("", title).strip()
        match = _EDITION_SUFFIX_RE.search(title) or _DISC_SUFFIX_RE.search(title)
        if match:
            edition = re.sub(r"\s+", " ", match.group("edition")).strip()
            if edition and edition not in editions:
                editions.insert(0, edition)
            title = title[:match.start()].strip()

    title = re.sub(r"\s+", " ", title).strip(" -–:+")
    if not title or title.lower() in {"the", "a", "an"}:
        title = original
        year = None
        formats = []
        editions = []

    return {
        "title": title,
        "year": year,
        "format": " + ".join(formats) if formats else None,
        "edition": " ".join(editions) if editions else None,
    }


def sanitize_barcode_movie_title(raw_title: str) -> tuple[str, int | None]:
    parsed = parse_barcode_movie_title(raw_title)
    return parsed["title"], parsed["year"]


def tmdb_search(query: str, year: int | None = None):
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": key, "query": query, **({"year": year} if year is not None else {})},
        timeout=10,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", [])[:20]:
        date = item.get("release_date") or ""
        results.append({
            "tmdb_id": item.get("id"),
            "title": item.get("title") or item.get("original_title") or "",
            "year": int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None,
            "overview": item.get("overview") or "",
            "poster_path": item.get("poster_path"),
        })
    return results


def barcode_product_lookup(upc: str):
    endpoint = (current_app.config.get("BARCODE_LOOKUP_URL") or "").strip()
    key = (current_app.config.get("UPCITEMDB_API_KEY") or "").strip()
    if endpoint:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        response = requests.get(endpoint, params={"upc": upc}, headers=headers, timeout=10)
    elif key:
        headers = {"user_key": key, "key_type": "3scale", "Accept": "application/json"}
        response = requests.get(
            "https://api.upcitemdb.com/prod/v1/lookup",
            params={"upc": upc},
            headers=headers,
            timeout=10,
        )
    elif current_app.config.get("UPCITEMDB_FREE_ENABLED", False):
        response = requests.get(
            "https://api.upcitemdb.com/prod/trial/lookup",
            params={"upc": upc},
            timeout=10,
        )
    else:
        return None

    if response.status_code == 404:
        return None
    response.raise_for_status()
    items = response.json().get("items") or []
    if not items:
        return None
    item = items[0]
    title = item.get("title") or ""
    parsed = parse_barcode_movie_title(title)
    return {
        "upc": upc,
        "product_title": title,
        "search_title": parsed["title"],
        "search_year": parsed["year"],
        "detected_format": parsed["format"],
        "detected_edition": parsed["edition"],
        "brand": item.get("brand"),
    }
