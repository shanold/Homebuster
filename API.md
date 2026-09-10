# Homebuster Mobile API v1

All authenticated calls use:

```
Authorization: Bearer <homebuster-device-token>
```

The token is issued by Homebuster and can be revoked without changing the user's password. Third-party API keys never leave the server.

## Authentication

- `POST /api/v1/auth/login` — username/password -> device token
- `POST /api/v1/auth/logout` — revoke current device token
- `GET /api/v1/me` — current user

## Library

- `GET /api/v1/movies?q=&format=&library_id=`
- `GET /api/v1/movies/<id>`
- `POST /api/v1/movies`
- `GET /api/v1/libraries`
- `GET /api/v1/shelves`
- `GET /api/v1/collections`
- `GET /api/v1/collections/<id>/movies`
- `GET /api/v1/loans`

## Lookup

- `GET /api/v1/tmdb/search?q=Alien`
- `GET /api/v1/barcodes/<UPC>`

Barcode lookup order:

1. Search the user's Homebuster collection for the UPC.
2. If found, return `status=owned` and the existing copy.
3. Otherwise, ask the configured server-side barcode provider.
4. Use the resulting product title to query TMDb on the server.
5. Return candidates to Android for confirmation before adding.
