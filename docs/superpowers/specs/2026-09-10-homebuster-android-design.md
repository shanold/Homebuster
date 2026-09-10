# Homebuster Android Companion Design

## Goal
Add an Android companion client to Homebuster for primarily browsing a user's movie collection, with camera barcode scanning for fast ownership checks and movie entry.

## Architecture
Homebuster remains the system of record. Android never connects to SQLite and never receives TMDb or barcode-provider credentials. A versioned Flask `/api/v1` layer exposes user-scoped library data and server-side lookup operations. Android stores only the server URL and a revocable device bearer token.

## Scope for v0.3
Android: connection/login, poster grid, search, movie details, collections, loans, UPC/EAN camera scanner, barcode result screen. Server: bearer-token auth, user-scoped reads, movie add endpoint, TMDb search proxy, barcode lookup that first checks local ownership.

## Security
Passwords are exchanged only with Homebuster login. Device tokens are random, hashed in SQLite on the server, and stored in encrypted preferences on Android. Third-party keys are Docker environment variables only. Internet deployments should use HTTPS.

## Barcode behavior
ML Kit performs only barcode decoding on-device. Homebuster first checks stored UPC values in the user's movies. Unknown UPCs may be sent from Homebuster to a configured provider. Provider result titles are then searched against TMDb server-side. Android confirms candidate selection before adding.
