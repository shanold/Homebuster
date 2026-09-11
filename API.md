# Homebuster Mobile API v1

This API is additive to the existing Flask web interface. It does not replace any browser routes or templates.

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `GET /api/v1/libraries`
- `GET /api/v1/shelves`
- `GET /api/v1/collections`
- `GET /api/v1/collections/{id}/movies`
- `GET /api/v1/movies`
- `GET /api/v1/movies/{id}`
- `POST /api/v1/movies`
- `GET /api/v1/loans`
- `GET /api/v1/tmdb/search?q=...`
- `GET /api/v1/barcodes/{upc}`

Authentication uses a revocable bearer token issued from the same Homebuster user account used on the web.


## Barcode lookup metadata

`GET /api/v1/barcodes/{upc}` preserves the barcode provider's raw product title while returning a structured `lookup` object with the cleaned TMDb title, optional year, format(s), language, Version / Edition, region, disc count, distributor removed from the search, and the staged TMDb search attempts. Results are ranked and the top candidate is also returned as `best_match`.

`POST /api/v1/movies` accepts `version`, `language`, `region`, and `disc_count` in addition to the existing movie fields, allowing the Android barcode confirmation flow to save detected physical-copy metadata without a schema migration.
