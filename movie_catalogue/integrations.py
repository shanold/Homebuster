from __future__ import annotations

import requests
from flask import current_app

from .barcode_parser import parse_barcode_product_title


def parse_barcode_movie_title(raw_title: str) -> dict:
    """Compatibility wrapper for the v0.3.7 parser API."""
    parsed = parse_barcode_product_title(raw_title)
    legacy_edition = parsed.edition
    if parsed.disc_count and parsed.edition:
        legacy_edition = f"{parsed.disc_count}-Disc {parsed.edition}"
    elif parsed.disc_count:
        legacy_edition = f"{parsed.disc_count}-Disc"
    return {
        "title": parsed.title,
        "year": parsed.year,
        "format": parsed.format,
        "edition": legacy_edition,
    }


def sanitize_barcode_movie_title(raw_title: str) -> tuple[str, int | None]:
    parsed = parse_barcode_product_title(raw_title)
    return parsed.title, parsed.year


def tmdb_search(query: str, year: int | None = None, media_type: str = "movie"):
    media_type = "tv" if str(media_type).lower() == "tv" else "movie"
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return []
    params = {"api_key": key, "query": query}
    if year is not None:
        params["first_air_date_year" if media_type == "tv" else "year"] = year
    endpoint = "tv" if media_type == "tv" else "movie"
    response = requests.get(
        f"https://api.themoviedb.org/3/search/{endpoint}",
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", [])[:20]:
        date = item.get("first_air_date") if media_type == "tv" else item.get("release_date")
        date = date or ""
        results.append({
            "tmdb_id": item.get("id"),
            "title": (item.get("name") or item.get("original_name") or "") if media_type == "tv" else (item.get("title") or item.get("original_title") or ""),
            "year": int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None,
            "overview": item.get("overview") or "",
            "poster_path": item.get("poster_path"),
            "media_type": media_type,
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
    brand = item.get("brand")
    parsed = parse_barcode_product_title(title, distributor_hint=brand)
    return {
        "upc": upc,
        "product_title": title,
        "search_title": parsed.title,
        "fallback_title": parsed.fallback_title,
        "search_year": parsed.year,
        "detected_formats": list(parsed.formats),
        "detected_format": parsed.format,
        "detected_edition": parsed.edition,
        "detected_language": parsed.language,
        "detected_region": parsed.region,
        "detected_disc_count": parsed.disc_count,
        "detected_distributor": parsed.distributor,
        "detected_category": parsed.category,
        "brand": brand,
    }


def tmdb_collection_search(query: str):
    query = (query or "").strip()
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key or not query:
        return []
    response = requests.get(
        "https://api.themoviedb.org/3/search/collection",
        params={"api_key": key, "query": query},
        timeout=10,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", [])[:20]:
        results.append({
            "id": item.get("id"),
            "title": item.get("name") or item.get("original_name") or "",
            "overview": item.get("overview") or "",
            "poster_path": item.get("poster_path"),
            "backdrop_path": item.get("backdrop_path"),
        })
    return results



def tmdb_movie_details(movie_id: int):
    """Return normalized TMDb movie details including official collection membership."""
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return None
    response = requests.get(f"https://api.themoviedb.org/3/movie/{int(movie_id)}", params={"api_key": key}, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    item = response.json()
    relation = item.get("belongs_to_collection")
    belongs = None
    if relation and relation.get("id"):
        belongs = {"id": int(relation["id"]), "name": relation.get("name") or "Collection"}
    return {
        "id": item.get("id"), "title": item.get("title") or item.get("original_title") or "",
        "release_date": item.get("release_date") or "", "poster_path": item.get("poster_path"),
        "belongs_to_collection": belongs,
    }

def tmdb_collection_details(collection_id: int):
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return None
    response = requests.get(
        f"https://api.themoviedb.org/3/collection/{int(collection_id)}",
        params={"api_key": key},
        timeout=10,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    item = response.json()
    parts = []
    for position, part in enumerate(item.get("parts") or []):
        parts.append({
            "id": part.get("id"),
            "title": part.get("title") or part.get("original_title") or "",
            "release_date": part.get("release_date") or "",
            "poster_path": part.get("poster_path"),
            "position": position,
        })
    return {
        "id": item.get("id"),
        "title": item.get("name") or item.get("original_name") or "",
        "overview": item.get("overview") or "",
        "poster_path": item.get("poster_path"),
        "backdrop_path": item.get("backdrop_path"),
        "parts": parts,
    }
