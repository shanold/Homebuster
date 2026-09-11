from __future__ import annotations

import re
from datetime import datetime
import requests
from flask import current_app

_MEDIA_TOKEN = r"(?:DVD|Blu[- ]?ray|4K(?:\s+UHD)?|UHD|Ultra\s+HD|Digital\s+Copy|Combo\s+Pack)"
_BRACKETED_MEDIA_RE = re.compile(rf"\s*[\[(]\s*{_MEDIA_TOKEN}\s*[\])]\s*", re.I)
_TRAILING_MEDIA_RE = re.compile(
    rf"(?:\s*[-–:+]\s*|\s+)(?:{_MEDIA_TOKEN})(?:\s*(?:\+|/|&)\s*(?:{_MEDIA_TOKEN}))*\s*$",
    re.I,
)
_TRAILING_YEAR_RE = re.compile(r"(?:\s*[\[(]?\s*)((?:19|20)\d{2})(?:\s*[\])])?\s*$")


def sanitize_barcode_movie_title(raw_title: str) -> tuple[str, int | None]:
    original = re.sub(r"\s+", " ", (raw_title or "").strip())
    if not original:
        return "", None

    title = original
    year = None
    year_match = _TRAILING_YEAR_RE.search(title)
    if year_match:
        candidate = int(year_match.group(1))
        if 1900 <= candidate <= datetime.now().year + 1:
            year = candidate
            title = title[:year_match.start()].strip()

    title = _BRACKETED_MEDIA_RE.sub(" ", title)
    previous = None
    while title != previous:
        previous = title
        title = _TRAILING_MEDIA_RE.sub("", title).strip()

    title = re.sub(r"\s+", " ", title).strip(" -–:+")
    if not title or title.lower() in {"the", "a", "an"}:
        title = original
        year = None
    return title, year


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
    clean, year = sanitize_barcode_movie_title(title)
    return {
        "upc": upc,
        "product_title": title,
        "search_title": clean,
        "search_year": year,
        "brand": item.get("brand"),
    }
