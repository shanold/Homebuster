from __future__ import annotations

import re
import requests
from flask import current_app


def tmdb_search(query: str):
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": key, "query": query},
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
    clean = re.sub(r"\s*[-–]\s*(Blu[- ]?ray|DVD|4K.*)$", "", title, flags=re.I).strip() or title
    return {
        "upc": upc,
        "product_title": title,
        "search_title": clean,
        "brand": item.get("brand"),
    }
