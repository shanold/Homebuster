import re
import requests
from flask import current_app


def tmdb_search(query):
    key = current_app.config.get('TMDB_API_KEY', '').strip()
    if not key:
        return []
    r = requests.get('https://api.themoviedb.org/3/search/movie', params={'api_key': key, 'query': query}, timeout=10)
    r.raise_for_status()
    out = []
    for item in r.json().get('results', [])[:20]:
        date = item.get('release_date') or ''
        out.append({
            'tmdb_id': item.get('id'),
            'title': item.get('title') or item.get('original_title') or '',
            'year': int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None,
            'overview': item.get('overview') or '',
            'poster_path': item.get('poster_path'),
        })
    return out


def barcode_product_lookup(upc):
    endpoint = current_app.config.get('BARCODE_LOOKUP_URL', '').strip()
    key = current_app.config.get('UPCITEMDB_API_KEY', '').strip()
    if endpoint:
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        r = requests.get(endpoint, params={'upc': upc}, headers=headers, timeout=10)
    elif key:
        headers = {'user_key': key, 'key_type': '3scale', 'Accept': 'application/json'}
        r = requests.get('https://api.upcitemdb.com/prod/v1/lookup', params={'upc': upc}, headers=headers, timeout=10)
    elif current_app.config.get('UPCITEMDB_FREE_ENABLED', False):
        r = requests.get('https://api.upcitemdb.com/prod/trial/lookup', params={'upc': upc}, timeout=10)
    else:
        return None
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    items = payload.get('items') or []
    if not items:
        return None
    item = items[0]
    title = item.get('title') or ''
    # Retail listings often append format/edition noise. Keep raw title too.
    clean = re.sub(r'\s*[-–]\s*(Blu[- ]?ray|DVD|4K.*)$', '', title, flags=re.I).strip() or title
    return {'upc': upc, 'product_title': title, 'search_title': clean, 'brand': item.get('brand')}
