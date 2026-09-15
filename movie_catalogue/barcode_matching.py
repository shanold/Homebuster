from __future__ import annotations

from .integrations import tmdb_search
from .barcode_parser import best_match_score, infer_copy_metadata_from_legacy_title, rank_tmdb_results, search_ready_title_candidates


def is_barcode_value(value: str) -> bool:
    digits = ''.join(ch for ch in str(value or '').strip() if ch.isdigit())
    return digits == str(value or '').strip() and len(digits) in (8, 12, 13, 14)


def barcode_tmdb_matches(product: dict, media_type: str = 'movie') -> tuple[list[dict], list[dict]]:
    raw_title = str(product.get('product_title') or '').strip()
    year = product.get('search_year')
    queries = []
    candidates = search_ready_title_candidates(raw_title, media_type=media_type)
    for value in (product.get('search_title'), *candidates, product.get('fallback_title')):
        title = str(value or '').strip()
        if title and not any(q.casefold() == title.casefold() and y == year for q, y in queries):
            queries.append((title, year))
    merged, attempts = {}, []
    for query_title, query_year in queries[:3]:
        ranked = rank_tmdb_results(query_title, query_year, tmdb_search(query_title, query_year, media_type=media_type))
        attempts.append({'title': query_title, 'year': query_year, 'results': len(ranked), 'best_score': best_match_score(ranked)})
        for item in ranked:
            key = item.get('tmdb_id') or (item.get('title'), item.get('year'))
            if key not in merged or int(item.get('match_score') or 0) > int(merged[key].get('match_score') or 0): merged[key] = item
        if best_match_score(merged.values()) >= 105: break
    results = sorted(merged.values(), key=lambda x: (-int(x.get('match_score') or 0), str(x.get('title') or '').lower()))[:20]
    for item in results:
        item['copy_metadata'] = infer_copy_metadata_from_legacy_title(raw_title, item.get('title') or '', media_type=media_type)
        item['media_type'] = media_type
    return results, attempts
