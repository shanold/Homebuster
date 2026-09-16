# Homebuster Developer Guide

This document is the map for humans reading or modifying Homebuster. It explains where the important code lives, how the major data types relate, and which rules are intentional. It is not a replacement for reading the code; it is the index that tells you where to start.

Homebuster is a self-hosted physical-media inventory application. The server is Flask + SQLite and serves both the browser UI and a JSON API used by the Android client. The server is authoritative for users, permissions, libraries, inventory, shelves, collections, box sets, and loans. The Android app is a client of that server rather than a second database.

## Architecture at a glance

```text
Browser
  |  Flask session + CSRF
  v
Flask blueprints --------------------------+
  auth.py                                  |
  libraries.py                             |
  catalog.py                               |--> db.py --> SQLite /data/movies.db
  box_sets.py                              |
  admin.py                                 |
                                           |
Android app                                |
  |  Bearer token                          |
  v                                        |
mobile_api.py -----------------------------+
        |
        +--> barcode_matching.py / barcode_parser.py
        +--> integrations.py --> TMDb / UPC provider
        +--> smart_collections.py
        +--> box_set_service.py
```

The browser and Android client deliberately use different authentication mechanisms. Browser pages use Flask-Login sessions and Flask-WTF CSRF protection. The mobile API uses bearer tokens stored as hashes on the server. `movie_catalogue/__init__.py` wires these systems together.

### Server code map

- `movie_catalogue/__init__.py` — application factory, blueprint registration, session invalidation, CSRF setup, health endpoint.
- `movie_catalogue/config.py` — environment-backed configuration and release version.
- `movie_catalogue/db.py` — SQLite connection management, schema creation, migrations, backups, initial admin bootstrap, CLI admin creation.
- `movie_catalogue/auth.py` — browser login, registration, logout, Flask-Login user loading.
- `movie_catalogue/permissions.py` — library owner/editor/viewer authorization helpers.
- `movie_catalogue/admin.py` — site-admin user management and protected user deletion/transfer flows.
- `movie_catalogue/libraries.py` — library creation/settings/membership/transfer/delete and reviewed TV-library moves.
- `movie_catalogue/catalog.py` — the main media catalogue: add/edit/delete, TMDb identification, shelves, loans, collections, CSV, and bulk match repair.
- `movie_catalogue/box_sets.py` — browser routes for physical movie box sets.
- `movie_catalogue/box_set_service.py` — reusable box-set creation, effective loan state, and loan rules shared by web/API code.
- `movie_catalogue/smart_collections.py` — TMDb-backed Smart Collection cache, suggestions, dismissals, approval, and automatic linking.
- `movie_catalogue/barcode_parser.py` — conservative parsing and normalization of product titles into searchable media titles and physical-copy metadata.
- `movie_catalogue/barcode_matching.py` — shared UPC-product-to-TMDb matching pipeline.
- `movie_catalogue/integrations.py` — outbound TMDb and barcode-provider HTTP calls.
- `movie_catalogue/mobile_api.py` — `/api/v1` contract consumed by Android.
- `movie_catalogue/templates/` — Jinja browser UI.
- `movie_catalogue/static/` — site CSS and image assets.

### Android code map

- `android/.../Api.kt` — Retrofit request/response models and API interface.
- `android/.../MainActivity.kt` — application-level Compose state, navigation, and most screens.
- `android/.../SessionStore.kt` — encrypted server URL/token storage plus small UI preferences.
- `android/.../ScannerScreen.kt` — camera barcode scanning.
- `android/.../HomebusterComponents.kt` — shared Compose UI pieces.
- `android/.../HomebusterTheme.kt` — visual theme.

## Database model

SQLite is the single source of truth. `db.py` enables foreign keys, a busy timeout, and WAL mode where supported. Schema updates are performed at application startup by `initialize_database()`.

The central relationships are:

```text
users
  | owns
  +---- libraries <---- library_members ---- users
          |
          +---- shelves
          |
          +---- movies ---- loans
          |       |
          |       +---- movie_collections ---- collections
          |       |
          |       +---- parent_box_set_id ---- box_sets
          |
          +---- box_sets ---- box_set_loans

TMDb cache tables support Smart Collections without repeatedly calling TMDb.
```

### Important table meanings

**`users`** stores username, password hash, admin/disabled flags, and `auth_version`. Increasing `auth_version` invalidates existing browser/mobile authentication associated with the older version.

**`libraries`** are top-level inventory containers. A library has exactly one owner and can additionally be shared through `library_members`. `default_media_type` influences add/search defaults; it does not rewrite the media already stored there.

**`movies`** represents physical owned inventory rows, despite the historical table name. A row can have `media_type='movie'` or `media_type='tv'`. Multiple physical copies of the same title remain separate rows and may be grouped only for display.

**`shelves`** belong to a library. `movies.shelf_id` is the user's physical-location assignment.

**`loans`** point to a specific physical `movies.id`, not a grouped title. This is why edit/loan/return UI must eventually resolve to a concrete copy.

**`collections` + `movie_collections`** represent organizational collections. A collection may be purely manual or may carry an official `tmdb_collection_id` when it represents a TMDb movie collection.

**`box_sets`** represent a physical set as an owned object. Contained films are first-class `movies` rows linked through `parent_box_set_id`, allowing individual contained films to participate in normal title behavior while preserving the physical parent.

The older `box_set_members` tables remain for migration/backward-compatibility history. `_migrate_box_set_members_to_movies()` promotes legacy lightweight members once and records a marker in `app_meta` so removed members are not recreated on every startup.

## Authentication and authorization

Homebuster has two authentication paths, but both ultimately check the same user and library data.

### Browser sessions

`auth.py` uses Flask-Login. A successful login stores the user's current `auth_version` in the Flask session. `create_app()` checks it on every browser request; if it no longer matches the user record, the session is cleared.

Registration is optional and controlled by `ALLOW_REGISTRATION`. Passwords are stored using Werkzeug password hashing. Password policy is centralized in `password_policy.py`.

### Mobile bearer tokens

`mobile_api.py` generates opaque tokens at login and stores only a SHA-256 hash in `api_tokens`. `token_required()` hashes the presented token, joins it to the user, rejects disabled users, and requires the token's stored `auth_version` to match the user's current `auth_version`.

The Android app keeps its token and server URL encrypted using Android Keystore-backed AES/GCM in `SessionStore.kt`. The server remains authoritative; the app does not persist a second inventory database.

### Library roles

Library roles are ordered:

```text
viewer < editor < owner
```

- **viewer** can read a shared library.
- **editor** can make normal inventory changes.
- **owner** can perform ownership/settings operations such as membership, transfer, deletion, and the TV-library move organizer.

Browser routes use `require_library_role()` from `permissions.py`. Mobile API routes perform equivalent role checks inside `mobile_api.py`. When adding a new mutation, do not rely on the UI hiding a button; enforce the role server-side.

Site admins are separate from library owners. Admin status grants access to site user-management functions; it is intentionally not a general backdoor into every user's private library.

## Media identification pipeline

Homebuster separates **physical-copy metadata** from **title identity**.

A barcode lookup normally flows like this:

```text
UPC/EAN
  -> integrations.barcode_product_lookup()
  -> raw product title
  -> barcode_parser.py
       - remove/recognize media-format terms
       - find edition/language/region/disc-count hints
       - generate conservative title candidates
  -> barcode_matching.barcode_tmdb_matches()
  -> integrations.tmdb_search()
  -> ranked TMDb candidates
  -> user review or high-confidence match
  -> physical copy saved as a movies row
```

The parser is deliberately conservative. Product listings often contain marketing text such as format, edition, studio, language, and disc count. The parser tries to remove those from the TMDb search title while retaining them as copy metadata where useful.

Movie and TV identification use the same general pipeline but pass a `media_type`. TMDb TV searches use TV endpoints and first-air-year semantics; movie searches use movie endpoints and release-year semantics.

The browser and Android barcode flows share server-side matching logic. If matching behavior changes, prefer changing the shared parser/matcher instead of inventing separate Android heuristics.

## Libraries, shelves, loans, and TV moves

A library move changes organization, not physical ownership metadata.

### TV move organizer

`libraries.py` provides the reviewed TV move workflow. Its rules are intentionally conservative:

1. Detection is automatic only for rows already identified with `media_type='tv'`.
2. Opening the review page changes nothing.
3. The user chooses the destination library.
4. The user explicitly selects which detected rows to move.
5. Only the submitted, still-TV rows in the source library are moved.
6. Shelf names are preserved. If the destination library lacks that shelf name, an equivalent shelf is created with its description/sort order.
7. Loan history for a moved row has its `library_id` updated so the loan and physical copy remain internally consistent.

This feature is for users who want smaller logical libraries without re-inventorying where media physically sits. Do not turn this into a silent automatic migration.

### Shelves

Shelves are library-scoped. A shelf assignment is stored on the physical media row. The Android shelf view is only a presentation choice; it does not create a separate shelf model.

### Loans

Loans always target a concrete physical copy. A grouped title in a UI may represent several `movies` rows; the loan/edit workflow must identify which copy is being changed. The database enforces one active loan per movie row.

For a contained box-set movie, effective availability also considers whether the entire parent box set is loaned. Shared rules live in `box_set_service.py` so the web and API paths do not disagree.

## Smart Collections and box sets

These features sound similar but model different real-world concepts.

### Smart Collections

Smart Collections are organizational groupings based on official TMDb movie-collection relationships. They do **not** infer franchises from similar titles.

Current suggestion policy:

- movie media only;
- at least two distinct owned TMDb movie IDs from a collection;
- at least 50% of the collection's released members owned;
- unreleased members are excluded from the denominator;
- dismissed suggestions are remembered per library;
- approved suggestions become normal `collections` rows carrying a `tmdb_collection_id`;
- later owned movies with the same official relationship can auto-link to an already approved collection.

Cache/backfill limits in `smart_collections.py` are there to keep a normal page request from turning into an unbounded burst of TMDb traffic. TMDb failures should not prevent the Collections page itself from loading.

### Physical box sets

A box set is physical inventory, not merely an organizational collection. It can carry its own barcode, format, edition/version metadata, shelf, and whole-set loan state. Contained movies are also first-class movie rows, enabling per-film loans and normal TMDb identity.

When code needs to reason about a box set or contained film's effective loan state, use `box_set_service.py` rather than duplicating conflict rules.

## Android client

The Android app intentionally delegates business rules to the server whenever practical.

### Main state/navigation

`HomebusterApp()` in `MainActivity.kt` owns top-level state:

- server URL and token;
- current screen;
- active library;
- selected title/copy/collection/shelf;
- server version and reauthentication state.

`detailsReturnScreen` records where a title detail page was opened from. This lets Back return to the shelf or collection that launched the detail instead of always jumping to the main Media screen.

### Grouped titles versus physical copies

`groupMovies()` groups rows for a cleaner poster grid. It does **not** create synthetic database records. `MovieGroup.copies` contains the real physical rows from the server. Mutations such as loan/edit/delete should use a selected real copy ID.

### Session expiration and server upgrades

There are two reauthentication mechanisms:

1. `ApiFactory` observes authenticated HTTP 401 responses and clears the local token.
2. On an existing authenticated startup, Android queries public `/api/v1/status`; if the stored server version differs from the current server version, it clears the token and asks the user to sign in again.

The server address is intentionally retained, so a server update should require credentials again without forcing the user to re-enter the URL.

Network failures are not authentication failures and must not automatically log the user out.

### Shelf case display

The Android shelf screen can render front-cover fake cases or spines. This is presentation only. The persisted `shelfViewMode` is a local UI preference in `SessionStore`; inventory remains on the server.

## Browser UI and templates

`base.html` contains the global shell/header. `header.css` is intentionally isolated and loaded after the main stylesheet because older header rules accumulated over earlier releases; new header work should prefer the isolated file rather than adding another competing rule to `styles.css`.

Library-level navigation lives in `_library_nav.html`. Feature pages use normal Jinja escaping; do not introduce `|safe` for user-controlled strings without a specific sanitization design.

POST forms are protected by Flask-WTF CSRF. The `/api/v1` blueprint is exempt because it authenticates with bearer tokens rather than browser cookies.

## Security boundaries and secrets

The repository can document how security works. It must not contain installation secrets.

Never commit:

- real `SECRET_KEY` values;
- TMDb or UPC provider API keys;
- production passwords or password-reset values;
- Android signing keystores or keystore passwords;
- bearer tokens;
- production databases or database backups containing user/inventory data;
- `.env` files containing secrets.

`SECRET_KEY` may be supplied through the environment. If it is omitted, Homebuster creates a random key beside the database and reuses that file. API provider keys stay on the server; Android calls Homebuster rather than embedding those provider credentials.

`SESSION_COOKIE_SECURE` defaults to false because Homebuster is commonly tested on local HTTP. For an Internet-facing HTTPS deployment, set it to true.

Security-sensitive rules belong on the server. Client-side validation and hidden buttons are usability aids, not authorization.

## Configuration

Runtime configuration lives in `movie_catalogue/config.py` and primarily comes from environment variables. Important values include:

- `DATABASE_PATH`
- `SECRET_KEY`
- `ALLOW_REGISTRATION`
- `PASSWORD_MIN_LENGTH`
- `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`
- `TMDB_API_KEY`
- `TMDB_POSTER_SIZE`
- `UPCITEMDB_API_KEY`
- `UPCITEMDB_FREE_ENABLED`
- `BARCODE_LOOKUP_URL`
- `PAGE_SIZE`
- `SESSION_COOKIE_SECURE`

Keep configuration parsing in `config.py` where possible rather than scattering direct environment reads throughout feature code.

## Migrations and backups

Homebuster currently performs lightweight in-place schema evolution in `db.py` rather than using a separate migration framework. `_ensure_catalog_columns()` adds columns/indexes introduced by later versions, and dedicated migration helpers handle structural changes such as promoting legacy box-set members.

Destructive browser operations such as deleting a library/user use database backups as an additional safety measure. `backup_database()` uses SQLite's backup API and writes timestamped files under a `backups` directory beside the main database.

When adding a schema field:

1. update the create-table definition for fresh installs;
2. add an idempotent migration for existing installs;
3. update any API/model serialization that needs the field;
4. add a regression test for both old and fresh schema expectations.

## Where to make common changes

| Goal | Start here | Usually also inspect |
| --- | --- | --- |
| Change login/registration | `auth.py` | `__init__.py`, `password_policy.py`, login/register templates |
| Change library permissions | `permissions.py` | corresponding browser route and `mobile_api.py` |
| Add library setting | `libraries.py` | `db.py`, `library_settings.html`, `config.py` if environment-backed |
| Change media add/edit behavior | `catalog.py` | `movie_form.html`, `mobile_api.py`, Android models |
| Change barcode parsing | `barcode_parser.py` | `barcode_matching.py`, matching tests |
| Change provider calls | `integrations.py` | `config.py`, error handling in caller |
| Change Smart Collections | `smart_collections.py` | collection routes/templates, cache schema |
| Change physical box sets | `box_set_service.py` / `box_sets.py` | `db.py`, `mobile_api.py` |
| Change shelf behavior | `catalog.py` | `libraries.py` for moves, Android shelf screens |
| Change loans | `catalog.py` / `box_set_service.py` | `mobile_api.py`, Android loan UI |
| Change API contract | `mobile_api.py` | `Api.kt`, Android callers, `API.md` |
| Change Android navigation | `MainActivity.kt` | `Screen`, Back handling, selected-state variables |
| Change header/filmstrip | `templates/base.html`, `static/header.css` | responsive breakpoints; avoid old competing rules |
| Add database column/table | `db.py` | serialization/forms/API/tests |

## Tests and release verification

The `tests/` directory contains both historical regression checks and newer release-specific source/behavior contracts. For a behavior change, use a test-first workflow: add a failing regression, implement the smallest change, then run the relevant older regressions.

Useful release verification includes:

- Python compilation;
- Jinja template parsing;
- focused standalone regressions for the changed feature;
- Android/Gradle compilation when a Gradle-capable environment is available;
- ZIP integrity for packaged releases.

A source-level brace/parenthesis check for Kotlin is only a structural sanity check. It is **not** a substitute for an actual Kotlin/Gradle compile.

## Readability conventions

Comments should explain **why**, boundaries, invariants, and non-obvious relationships. Avoid comments that simply restate the next line of code.

Prefer:

```python
# Loans follow a moved physical copy so history stays scoped to the copy's new library.
```

over:

```python
# Update loans.
```

Keep names explicit, keep shared business rules in shared server helpers, and update this guide when a new subsystem changes the architecture enough that a future maintainer would otherwise have to rediscover it.
