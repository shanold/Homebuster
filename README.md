# Homebuster Mobile v0.3 source

This package adds the first Android companion-client architecture for Homebuster.

## What is included

- `server/` — Flask/SQLite Homebuster mobile API reference implementation and Docker test service.
- `android/` — native Kotlin + Jetpack Compose Android client.
- `API.md` — `/api/v1` contract used by the Android app.
- `.env.example` — server-only secret/configuration variables.

## Android v0.3 features

- Save the Homebuster server URL.
- Sign in with an existing Homebuster username/password.
- Store a revocable Homebuster device token in encrypted preferences.
- Browse/search movies in a responsive poster grid.
- Open movie details including year, format, runtime, overview and stored UPC.
- View collections and current/returned loans.
- Scan UPC-A, UPC-E, EAN-8 and EAN-13 with the phone camera.
- If the scanned UPC is already in the user's library, show the owned copy immediately.
- Unknown barcodes are looked up by the Homebuster server, never directly by Android.

## Secret handling

The Android source contains no TMDb key and no barcode-provider key.

Server environment variables:

- `TMDB_API_KEY`
- `UPCITEMDB_API_KEY` (optional paid UPCitemdb account)
- `UPCITEMDB_FREE_ENABLED=true` (optional no-key trial endpoint)
- `BARCODE_LOOKUP_URL` (optional custom server-side provider)
- `SECRET_KEY`
- `PASSWORD_MIN_LENGTH`

## Run the reference server

```bash
cd server
cp ../.env.example .env
# copy the values you want into docker-compose.yml or use an env_file entry
docker compose up -d --build
```

Health check:

```bash
curl http://YOUR-SERVER:8080/api/v1/health
```

## Open/build Android

Open the `android/` directory in current Android Studio and let Gradle sync. This source targets API 37 and JDK 17.

For a LAN-only Homebuster install, URLs such as `http://192.168.1.20:8080` are accepted. For access over the internet, put Homebuster behind HTTPS; do not expose the raw Flask/Gunicorn port directly.

Build a debug APK from Android Studio, or with a local Gradle 9.6 installation:

```bash
gradle :app:assembleDebug
```

The APK will be under `android/app/build/outputs/apk/debug/`.

## Barcode flow

```text
Phone camera
   ↓
ML Kit decodes UPC/EAN locally
   ↓
Android sends only the barcode number to Homebuster
   ↓
Homebuster checks the user's SQLite collection
   ↓
Already owned? ── yes → return owned copy
   │
   no
   ↓
Homebuster asks configured UPC provider
   ↓
Homebuster searches TMDb using the product title
   ↓
Android receives candidate movie(s) for confirmation
```

## Current development-package note

The server directory here is deliberately isolated as a reference/test implementation of the v1 API. The intended production integration is to register the same `mobile_api` blueprint inside the existing Homebuster Flask application so the web UI and Android client share the existing Homebuster SQLite database rather than running two databases.
