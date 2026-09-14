# Homebuster

A community fork/rework of [TheMarveled/movie-cataloguer](https://github.com/TheMarveled/movie-cataloguer), focused on self-hosted personal and shared physical movie collections.

The original project is MIT licensed. This fork keeps the physical-media catalogue idea and core movie metadata while adding accounts, private/shared Libraries, permissions, Shelves, and Loans.

## What is new

- Username/password login with no email requirement.
- Optional public registration controlled by `ALLOW_REGISTRATION=true|false`.
- Site admins can reset passwords, disable accounts, grant/revoke admin status, and safely delete users.
- Site-admin status **does not grant access to users' Movie Libraries**.
- Every account can own multiple private Libraries and join shared Libraries.
- Shared Library roles: **Owner**, **Editor**, and **Viewer**.
- Library ownership can be transferred, including a completely private Library.
- Safe user deletion: every owned Library must be transferred or deliberately deleted first.
- Shelves for physical organization, including an Unassigned state.
- Loans with borrower name, optional phone, loan date, notes, return action, and retained history.
- Existing-style Collections for franchises/groups such as `Evil Dead`.
- Search and filters for status, format, shelf, collection, and loan availability.
- CSV import/export per Library.
- TMDb identification for title/year/poster when `TMDB_API_KEY` is configured.
- TMDb-first Add Movie search with a manual-entry fallback.
- SQLite WAL mode and automatic backups before destructive Library/user operations.
- Legacy Movie Cataloguer database migration.
- Docker/Compose deployment using a persistent `./data` directory.

## Quick Docker start

```bash
cp .env.example .env
mkdir -p data
```

Edit `.env` before the first start. At minimum, give the initial admin a real password:

```env
ALLOW_REGISTRATION=false
PASSWORD_MIN_LENGTH=8
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=use-a-long-unique-password-here
```

Then run:

```bash
docker compose up -d --build
```

Open:

```text
http://YOUR-SERVER-IP:8092
```

After the admin account has been created successfully, remove `INITIAL_ADMIN_PASSWORD` from `.env` (or leave it blank) and restart the container. Existing accounts are not overwritten by the bootstrap variables.

### Create or promote an admin from the CLI

You can also create a site admin without using bootstrap environment variables:

```bash
docker compose exec homebuster flask --app app create-admin admin
```

The command prompts for the password without echoing it. If that username already exists, it resets the password and grants site-admin status.

The Docker container is named `Homebuster`, so its logs can be viewed with `docker logs Homebuster`. Homebuster also identifies itself by name in its startup log.

## Registration

Registration defaults to disabled:

```env
ALLOW_REGISTRATION=false
PASSWORD_MIN_LENGTH=8
```

`PASSWORD_MIN_LENGTH` controls the minimum password length for registration, admin password resets, first-boot admins, and the `create-admin` CLI command.

Turn it on when you want new users to create accounts:

```env
ALLOW_REGISTRATION=true
```

No email address is collected. Each registration automatically creates a private `My Movies` Library.

## Permissions

Permissions belong to a Library, not to the site account globally.

| Role | View | Add/edit/delete movies | Shelves/Collections/Loans | Share/manage members | Transfer/delete Library |
|---|---:|---:|---:|---:|---:|
| Viewer | Yes | No | No | No | No |
| Editor | Yes | Yes | Yes | No | No |
| Owner | Yes | Yes | Yes | Yes | Yes |

A site admin can manage user accounts but cannot open a Library unless its owner explicitly shares that Library with the admin's normal user account.

## Migrating an existing `movies.db`

The original Movie Cataloguer database can be migrated in place.

1. Stop the old application.
2. Make your own backup of `movies.db` first.
3. Copy the old database to this fork as:

```text
./data/movies.db
```

4. Set `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` for the first boot. The migrated movies need an account to own their new Library.
5. Run `docker compose up -d --build`.

On startup, the app detects the old `movies` table because it has no `library_id`. It creates an automatic `pre-migration-*.db` backup under:

```text
./data/backups/
```

Then it migrates the movie rows into the initial account's `My Movies` Library. Existing movie integer IDs and existing Collection IDs/relationships are preserved.

The migrated fields include the original project's:

- barcode
- title
- year
- format
- poster path
- TMDb ID
- owned/wanted status
- version/edition
- country
- language
- region
- disc count
- notes
- Collections and movie/Collection links

## Backups

Before clearing a Library, deleting a Library, or deleting a user, the app creates a SQLite backup in:

```text
./data/backups/
```

These are not a replacement for your normal off-site backups. Back up the entire `./data` directory with the rest of your server data.

Keep the live SQLite database on a local filesystem. Backing it up to SMB/NFS is fine, but avoid running the live `movies.db` directly from a network share.

## Reverse proxy / Internet hosting

For Internet exposure, put the container behind HTTPS with your existing reverse proxy. When the browser always reaches the site through HTTPS, set:

```env
SESSION_COOKIE_SECURE=true
```

The app uses HTTP-only, SameSite=Lax session cookies and CSRF protection for state-changing forms.

Do not expose Flask's development server. The Docker image runs Gunicorn.

## TMDb

Set an API key in `.env`:

```env
TMDB_API_KEY=your_key_here
```

From a movie's detail page, Editors and Owners can choose **Identify with TMDb** and select the correct search result. This updates the movie's title, year, poster, and TMDb ID.

## CSV

CSV export is scoped to the Library currently open. Imports support the original metadata plus two useful columns:

- `shelf` — shelf name; missing shelves are created automatically.
- `collections` — semicolon-separated Collection names.

Export columns:

```text
barcode,title,year,format,poster_path,tmdb_id,status,version,country,language,region,disc_count,notes,shelf,collections
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_PATH="$PWD/data/movies.db"
export ALLOW_REGISTRATION=true
flask --app app create-admin admin
flask --app app run --debug
```

Run tests with:

```bash
pytest -q
```

## Project layout

```text
app.py
movie_catalogue/
  __init__.py
  admin.py
  auth.py
  catalog.py
  config.py
  db.py
  libraries.py
  permissions.py
  static/styles.css
  templates/
tests/
Dockerfile
docker-compose.yml
.env.example
```

## Notes about this first fork

The original project had a large single-page JavaScript UI including bulk-edit operations. This rework intentionally prioritizes the new multi-user security model and the core catalogue workflows in smaller Flask modules. Movie CRUD, metadata, search/filtering, CSV, Collections, and TMDb matching are present, but the original bulk-edit toolbar is not yet reproduced.

## Attribution and license

Based on **Movie Cataloguer** by TheMarveled:

https://github.com/TheMarveled/movie-cataloguer

Released under the MIT License. See `LICENSE`.





## v0.3.22 persistent review queue

Bulk Match / Repair now stores a persistent `review_pending` flag for movies that could not be matched automatically. The Library page shows **Review unmatched movies (N)** whenever the library has pending review work, so you can leave and return later without running Match / Repair again. **Skip for now** keeps the movie in the queue, a successful TMDb match clears it automatically, and **Dismiss from review** removes an intentionally unmatched movie from the queue. Existing databases add the new flag automatically on startup. This is a server-side update; Android remains v0.3.20 (versionCode 15).

## v0.3.21 review workflow

Bulk Match / Repair turns its completion action into a real review workflow. If automatic matching leaves movies needing review, the completion button opens a review queue. Each movie can be matched against TMDb using the same smart candidate/metadata pipeline, skipped for the current pass, and the queue automatically advances after a selection.

## v0.3.20 scanner shared matching pipeline

The Android barcode scanner now uses the same search-ready title candidate pipeline as single-movie Identify and bulk Match / Repair. Strong physical-copy metadata such as format, disc count, edition, region, and packaging is removed from TMDb search candidates even when it appears in mixed order. After TMDb results are returned, Homebuster anchors metadata recovery to each result's canonical title and Android saves the metadata belonging to the specific result selected by the user. Common catalog spelling `Blue-ray` is normalized to `Blu-ray`. Android is v0.3.20 (versionCode 15), so this release requires rebuilding the signed release APK with the existing Homebuster keystore.

## v0.3.19 canonical metadata repair and visible bulk progress

Identify and **Match / Repair Movies** now use the TMDb-confirmed canonical movie title as an anchor to recover physical-copy metadata from noisy legacy names. Format, Edition, Language, Region, and Disc Count are filled into their dedicated fields only when the existing value is blank or `Unknown`; manual corrections are preserved. Metadata can appear in mixed order, and disc counts accept both numeric and word forms such as `2 Disc` and `two disk`.

Bulk Match / Repair now runs on a progress page in small committed batches instead of one long silent request. The page reports processed, matched, refreshed, metadata-repaired, review-needed, and failed counts. Automatic matching remains high-confidence-only, and unmatched movies use at most three TMDb search requests before Homebuster gives up and leaves the entry for manual review. This is a server-only release; the Android companion remains v0.3.16.

## v0.3.18 smarter legacy-title matching

Identify and **Match / Repair Movies** now try multiple conservative TMDb search candidates instead of relying on one strictly parsed title. Old library entries can recover from combined media wording, trailing parenthetical notes, generic edition labels, collection labels, and very small title typos. Candidate cleanup never rewrites the stored title by itself; a title changes only after a TMDb match is selected or accepted at high confidence. Bulk matching remains conservative and leaves ambiguous remakes/box sets unmatched.

Examples now handled for search include `Beauty and the beast, DVD and Blu-ray` -> `Beauty and the beast`, `Bambi Diamond Edition` -> `Bambi`, and `An American Tale(Fievel)` -> `An American Tale`.

## v0.3.17 matching cleanup

The web **Identify** and **Match / Repair Movies** flows now run unmatched legacy titles through the same conservative barcode-title parser used by the scanner before querying TMDb. The stored title is not changed unless a match is accepted. This is a server-only change; the Android companion remains v0.3.16.

## Android companion app (v0.3.20)

- Android respects system status/navigation bar safe areas on modern Android.
- Grouped movie posters collapse multiple physical formats of the same title into one library card while keeping copies separate in details.
- Barcode lookup detects title, year, format, language, edition, region, disc count, and common distributor noise before TMDb search.
- TMDb candidates are ranked by title/year similarity, with progressively broader fallback searches only when needed.
- The barcode confirmation screen shows what Homebuster detected and can add the selected TMDb match with the detected physical-copy metadata.
- Web header uses the Homebuster house/film-strip icon.

The existing Homebuster web interface remains the primary browser interface. The `android/` directory contains a companion Android client that connects to the same Flask server and SQLite database through `/api/v1`.

Third-party service credentials stay on the server. The Android APK stores only the Homebuster server URL and its revocable login token. Configure TMDb and optional barcode lookup keys in the server `.env`; never put them in the Android project.

For quick development, build a debug APK with Android Studio or `./gradlew assembleDebug`.

For normal phone installs, use a consistently signed release APK. One-time setup and build instructions are in:

```text
android/RELEASE_SIGNING.md
```

After the signing key is configured, build with `./gradlew assembleRelease`.

## v0.3.23 faster Match / Repair and corrected-title review search

- Match / Repair now processes only unresolved or pending-review movies by default.
- The scan screen includes an off-by-default **Refresh metadata for already matched movies** option. Enable it when you intentionally want to refresh TMDb-derived title/year/poster data for matched entries.
- Progress totals reflect the selected scan mode instead of always using the full library size.
- The persistent review queue now has an editable TMDb search-title box, so spelling/title corrections can be searched without leaving the review workflow.
- Android is unchanged from v0.3.20 / versionCode 15 for this server-only release.

## v0.3.24 TV / box-set inventory support

Homebuster can now inventory either **Movies** or **TV / Box Sets** while keeping the existing physical-copy model. Existing database rows migrate automatically to `media_type=movie`. Movie remains the default TMDb search everywhere; Homebuster only uses TMDb TV when the user explicitly selects TV / Box Set, avoiding an automatic double-search of both APIs.

Web Add, Identify, and the persistent Match / Repair review queue have a Movie/TV selector. TV results normalize TMDb's series name and first-air year into Homebuster's existing title display. Once matched, the item remembers its media type, and optional matched-metadata refresh uses the correct Movie or TV endpoint. Grouping uses both media type and TMDb ID so a movie and TV series with the same numeric TMDb ID cannot collide. CSV import/export also preserves media type.

Android is updated to **v0.3.24 (versionCode 16)**. Movie/TV identity is carried through the API, collection grouping, details/cards, barcode search, and Add this copy. Barcode lookup defaults to Movie; selecting TV / Box Set explicitly reruns the match against TMDb TV. Continue signing release APKs with the same existing Homebuster release keystore.

The Match / Repair **Refresh metadata for already matched movies** checkbox is also visually corrected so the checkbox sits inline with its label. It remains off by default.


## v0.3.25 TV season / box-set parsing

TV searches now treat trailing inventory descriptors such as `Season 1`, `Complete First Season`, `Complete Series`, `Box Set`, and collection-style set suffixes as copy metadata rather than part of the TMDb series title. For example, `Castle Season 1` searches TMDb TV for `Castle` and, after selection, stores `Season 1` in Edition. Movie searches remain unchanged. The shared TV-aware parser is used by web Identify/review/bulk matching and the Android-facing barcode API. Android is v0.3.25 (versionCode 17).

## v0.3.26 Identify TV override fix

- Fixes **Identify with TMDb** when an existing row is still stored as Movie but the user switches the Identify page to TV.
- The selected Movie/TV mode now controls title candidate parsing before TMDb search.
- Example: `Castle Season 1` + TV now searches `Castle`, then preserves `Season 1` as copy metadata when selected.
- Android remains v0.3.25 / versionCode 17; this is a server/web Identify-path fix.

## v0.3.27 — Physical Movie Box Sets / TMDb Collections

Homebuster now supports physical movie box sets as first-class inventory items. A box set owns the real barcode, shelf, format, edition, region/language, disc count, notes, and loan state, while TMDb Collection data can populate the canonical films contained inside it. Contained films are hidden from the main library grid by default but remain searchable; a per-library setting can show them as clearly labeled **In box set** cards while keeping the parent box-set card visible.

Whole box sets and individual contained films can be loaned. An individual film loan marks the parent incomplete and blocks a whole-set loan until it returns; a whole-set loan makes every contained film effectively unavailable without creating fake child loan records. Homebuster intentionally does not track which exact physical disc contains each movie. Existing user-created Homebuster Collections remain separate from physical Movie Box Sets / TMDb Collections.

The server API includes first-class box-set and TMDb Collection endpoints plus explicit barcode `media_type=collection` lookup. Android box-set UI is intentionally deferred for this web/server-first release; existing Android release signing behavior is unchanged.

## v0.3.28 — First-Class Movies Inside Physical Box Sets

- Films contained in a physical movie box set are now normal Homebuster movie records linked to the parent set.
- Opening a box set shows clickable films that use the normal movie detail page and normal borrower/phone/date/notes loan workflow.
- Parent box-set physical data (barcode, format, shelf, region, edition and disc count) is inherited for contained-film display instead of being duplicated on each child.
- Whole-set loans make every child show **Loaned with box set**; an individual child loan blocks whole-set checkout, and a whole-set loan blocks child checkout.
- Contained films remain hidden from the main grid by default, can be enabled in Library Settings, and are always searchable.
- **Identify with TMDb** and persistent **Review unmatched titles** now include **Movie Collection / Box Set**, using TMDb Collection search without probing Movie/TV endpoints automatically.
- Existing v0.3.27 lightweight box-set members and member-loan history are promoted idempotently on startup into first-class movie rows and standard movie loans.
- Movie CSV now records parent box-set linkage; Box Set CSV continues to recreate the parent and its contained films.

## v0.3.29 — Identify search QoL and combo-pack metadata

Identify with TMDb now has an editable search-title field, matching the persistent review workflow, so an imported or scanned title can be corrected without leaving the Identify screen. TMDb movie/TV searches first use the stored year when available; if that constrained search returns no results, Homebuster retries the same cleaned title on the same endpoint without the year. This fallback is also used by bulk high-confidence matching. Movie Collection searches remain collection-only and do not fan out across endpoints.

Blu-ray/DVD combo packs remain a single physical inventory copy. Common scan spellings such as `Blu-ray DVD`, `Blu-ray + DVD`, `Blu-ray/DVD`, `Blu Ray DVD`, and `Blue-ray DVD` normalize to format **Blu-ray + DVD**, while edition metadata such as **Diamond Edition** remains separate. Manual movie entry now includes **Blu-ray + DVD** in the Format selector. Android source/signing behavior is unchanged from v0.3.25 / versionCode 17.


## v0.3.30 — Manual Match Control + Bulk Shelf Sorting

- Match / Repair can keep automatic high-confidence matching enabled (default) or queue every unmatched title for human review.
- Shelf pages now support bulk adding and removing movies.
- Add-to-shelf defaults to unshelved movies only; an optional toggle shows movies on other shelves for moving.
- Deleting a shelf explicitly unassigns its movies and box sets; it never deletes inventory titles.


## v0.3.31 — Import Hub + Bulk TMDb Search Type
- Moves CSV import controls off the main library toolbar into a dedicated Import page.
- Match / Repair can explicitly search Movie, TV / Box Set, or Movie Collection / Box Set for unresolved titles.
- Bulk collection matches use the existing physical box-set conversion flow.
- Already matched titles still refresh using their stored Movie/TV identity.


## v0.3.32 — Interactive Shelf View
- Shelf pages can switch between the familiar list view and a visual bookshelf view.
- Shelf View creates compact Homebuster-generated spines from the poster art already stored for each title; it does not depend on unavailable real package-spine artwork.
- Clicking a shelf spine opens a full-poster case preview with the physical media format banded across the top and a link to normal details/loan actions.
- A live 10–40 movies-per-row slider changes shelf density immediately and adapts to narrower screens.
- View mode and density are remembered in the browser with localStorage.
- List View adds a subtle cropped poster-art slice in the unused background area while keeping metadata readable.


## v0.3.33 — Reliable Shelf Toggle + Export Hub
- Shelf View controls no longer depend on localStorage being available; view switching and density controls still work when browser storage is blocked or unavailable.
- View and density persistence remain best-effort when localStorage is available.
- The main library toolbar now has one Export button leading to a dedicated Export page for Movies CSV and Box Sets CSV downloads.


## v0.3.34 — Shelf View display fix + brighter list artwork
- Fixes the Shelf View toggle when component CSS such as `.list-cards { display: flex; }` overrides the browser default styling of the HTML `hidden` attribute. Homebuster now gives `[hidden]` an explicit `display: none !important` rule.
- Brightens the poster-derived artwork in Shelf List View while keeping a stronger dark gradient behind title and metadata text.


## v0.3.35 — Shelf pagination, taller cases, brighter artwork

- Shelf View now shows four visual rows per page. The Movies per row slider dynamically sets the page size to four times the effective row density.
- List View now shows 50 movies per page. Both modes have Previous/Next controls and a page indicator.
- Shelf cases are roughly 50% taller and both List and Shelf artwork treatments are brighter.
