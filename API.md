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
