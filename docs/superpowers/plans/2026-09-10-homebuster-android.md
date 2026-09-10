# Homebuster Android Companion Implementation Plan

**Goal:** Add a versioned mobile API to Homebuster and a native Android client for browsing and barcode scanning.

**Architecture:** Flask remains the single owner of SQLite and all third-party credentials. Android is a token-authenticated API client and performs only local camera barcode decoding.

**Tech Stack:** Flask, SQLite, Docker/Gunicorn, Kotlin, Jetpack Compose, Retrofit, CameraX, ML Kit barcode scanning, Coil.

**Spec:** `docs/superpowers/specs/2026-09-10-homebuster-android-design.md`

## Global Constraints
- No TMDb or UPC-provider key in the APK.
- Mobile data is user-scoped.
- Existing Homebuster browser sessions remain separate from device bearer tokens.
- Barcode matching checks the local user's collection before any provider call.
- API is versioned under `/api/v1`.

## Tasks
- [x] Define mobile API contract and token model.
- [x] Add server-side user-scoped movie, collection, loan, TMDb and barcode routes.
- [x] Add local UPC ownership lookup.
- [x] Add server-only provider configuration.
- [x] Scaffold native Android project.
- [x] Add server connection and login/session storage.
- [x] Add movie grid/search and movie detail view.
- [x] Add collections and loans views.
- [x] Add CameraX + bundled ML Kit barcode scanner.
- [x] Add barcode result flow.
- [x] Package source and API documentation.
