# Homebuster Smart Collections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add movie-only TMDb-backed Smart Collection recommendations, persistent dismissals, automatic collection maintenance, physical box-set integration, bounded TMDb refresh/backfill, and the uppercase purple/yellow-glow HOMEBUSTER wordmark for v0.3.41.

**Architecture:** Keep approved Smart Collections as ordinary rows in the existing `collections` table, identified by an optional `tmdb_collection_id`. Add a focused TMDb membership cache plus library-scoped dismissal state so recommendation computation is local and repeated Collections page visits do not cause repeated API calls. Put recommendation/backfill/linking logic in a dedicated service module, then call that service from web collection routes and every physical box-set creation path.

**Tech Stack:** Python 3 / Flask, SQLite, Jinja2, requests, existing standalone source-contract tests, existing pytest suite when Flask dependencies are available.

**Spec:** `docs/superpowers/specs/2026-09-14-smart-collections-design.md`

## Global Constraints

- Target server release is `0.3.41`; Android `versionName`/`versionCode` remain unchanged.
- Smart Collections are movie-only; do not add TV Smart Collection logic.
- Eligibility requires at least 2 distinct owned TMDb movie IDs and at least 50% of released TMDb collection members.
- Only owned Homebuster movie rows are linked into organizational Collections; never create placeholder/unowned movie rows.
- Physical box-set parent rows are never members of organizational Collections; contained first-class `movies` rows are.
- Library-scoped Smart Collections setting defaults enabled for existing and new libraries.
- Dismissals are persistent and library-scoped; Show dismissed is a view toggle and restore clears dismissal state.
- Do not infer TMDb identity from collection names.
- No Movie + TV + Collection endpoint fan-out.
- TMDb collection-detail refresh is throttled to at most once per 24 hours per known collection.
- Existing-library membership backfill must be bounded per request and persist progress via cache rows; no background-worker subsystem.
- TMDb failures must not prevent viewing/managing existing Collections.
- Android gets no Smart Collection recommendation UI; existing approved collections remain visible through existing collection APIs.
- Header wordmark becomes `HOMEBUSTER`; login-page image is unchanged.

---

## File Structure

- **Create `movie_catalogue/smart_collections.py`** — sole owner of Smart Collection cache, eligibility, approval/dismissal/restore, auto-linking, box-set organizational collection synchronization, bounded backfill, and 24-hour collection refresh decisions.
- **Modify `movie_catalogue/db.py`** — schema/migration only: library setting, TMDb-backed collection metadata, cache table, dismissal table, indexes.
- **Modify `movie_catalogue/integrations.py`** — expose normalized movie-detail collection relationship and released collection-part semantics without changing endpoint fan-out.
- **Modify `movie_catalogue/catalog.py`** — Collections-page orchestration/actions and hooks after movie identification succeeds.
- **Modify `movie_catalogue/box_set_service.py`** — synchronize contained movie rows into the matching organizational collection inside box-set create/convert transactions.
- **Modify `movie_catalogue/libraries.py`** and **`movie_catalogue/templates/library_settings.html`** — library setting route/UI.
- **Modify `movie_catalogue/templates/collections.html`** — suggestion cards, dismissed toggle, backfill status, restore/create/dismiss controls.
- **Modify `movie_catalogue/templates/base.html`** and **`movie_catalogue/static/styles.css`** — uppercase wordmark + restrained yellow glow.
- **Modify `movie_catalogue/config.py`**, **`README.md`** — v0.3.41 version/release notes.
- **Create `tests/standalone_v0341_smart_collections_schema_checks.py`** — schema/source contracts.
- **Create `tests/standalone_v0341_smart_collections_behavior.py`** — SQLite-only service behavior using monkeypatched TMDb callbacks where possible.
- **Create `tests/standalone_v0341_smart_collections_ui_checks.py`** — routes/templates/branding/source contracts.
- **Modify older standalone version-acceptance checks** that currently cap accepted server versions at 0.3.40.

---

### Task 1: Add Smart Collection schema and migration

**Files:**
- Modify: `movie_catalogue/db.py`
- Create: `tests/standalone_v0341_smart_collections_schema_checks.py`

**Interfaces:**
- Produces library column `smart_collections_enabled INTEGER NOT NULL DEFAULT 1`.
- Produces collection columns `tmdb_collection_id`, `tmdb_collection_name`, `tmdb_last_refreshed_at`.
- Produces `tmdb_movie_collection_cache(tmdb_movie_id PRIMARY KEY, tmdb_collection_id, tmdb_collection_name, checked_at)`.
- Produces `smart_collection_dismissals(library_id, tmdb_collection_id, dismissed_at, PRIMARY KEY(library_id,tmdb_collection_id))`.
- Produces unique partial index on `(library_id, tmdb_collection_id)` for non-null TMDb-backed collections.

- [ ] **Step 1: Write the failing schema contract test**

Create `tests/standalone_v0341_smart_collections_schema_checks.py` that reads `movie_catalogue/db.py` and asserts the exact new column/table/index names exist. Include checks that `smart_collections_enabled` defaults to `1`, the cache primary key is `tmdb_movie_id`, the dismissal key is `(library_id,tmdb_collection_id)`, and the collection uniqueness index is partial (`WHERE tmdb_collection_id IS NOT NULL`).

- [ ] **Step 2: Run the test and verify RED**

Run:
```bash
python tests/standalone_v0341_smart_collections_schema_checks.py
```
Expected: FAIL because the v0.3.41 schema names are absent.

- [ ] **Step 3: Extend table creation and additive migrations**

In `_create_identity_tables()` add:
```sql
smart_collections_enabled INTEGER NOT NULL DEFAULT 1
```
to new-library creation.

In `_create_catalog_tables()` extend `collections` with:
```sql
tmdb_collection_id INTEGER,
tmdb_collection_name TEXT,
tmdb_last_refreshed_at TEXT
```
and create:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_collections_library_tmdb_unique
ON collections(library_id, tmdb_collection_id)
WHERE tmdb_collection_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS tmdb_movie_collection_cache (
    tmdb_movie_id INTEGER PRIMARY KEY,
    tmdb_collection_id INTEGER,
    tmdb_collection_name TEXT,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tmdb_movie_collection_cache_collection
ON tmdb_movie_collection_cache(tmdb_collection_id);

CREATE TABLE IF NOT EXISTS smart_collection_dismissals (
    library_id INTEGER NOT NULL,
    tmdb_collection_id INTEGER NOT NULL,
    dismissed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(library_id, tmdb_collection_id),
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
);
```

Follow the existing additive-migration helpers in `db.py` to add the new library/collection columns to v0.3.40 databases without rebuilding tables. Do not rely only on the CREATE TABLE definitions.

- [ ] **Step 4: Run the schema test**

Run:
```bash
python tests/standalone_v0341_smart_collections_schema_checks.py
```
Expected: PASS.

- [ ] **Step 5: Run existing migration checks**

Run:
```bash
python tests/standalone_v0328_sqlite_migration_behavior.py
python tests/standalone_v0339_library_default_schema_checks.py
```
Expected: PASS.

- [ ] **Step 6: Commit if working in Git**

```bash
git add movie_catalogue/db.py tests/standalone_v0341_smart_collections_schema_checks.py
git commit -m "feat: add smart collection schema"
```
If the extracted source is not a Git repo, record the checkpoint in the implementation notes instead of claiming a commit.

---

### Task 2: Normalize TMDb collection metadata and released-member counting

**Files:**
- Modify: `movie_catalogue/integrations.py`
- Test: `tests/standalone_v0341_smart_collections_behavior.py`

**Interfaces:**
- Produces `tmdb_movie_details(movie_id: int) -> dict | None` with normalized `belongs_to_collection`.
- Extends `tmdb_collection_details(collection_id)` parts with enough release data to determine released members.
- `smart_collections.py` will consume only normalized dictionaries, not raw requests responses.

- [ ] **Step 1: Write failing integration-normalization tests**

In `tests/standalone_v0341_smart_collections_behavior.py`, monkeypatch `requests.get` (or inspect normalized helper output if a request seam already exists) and assert movie detail normalization produces:
```python
{
    "id": 11,
    "title": "Example",
    "release_date": "2020-01-01",
    "poster_path": "/poster.jpg",
    "belongs_to_collection": {"id": 99, "name": "Example Collection"},
}
```
Also assert a movie with `belongs_to_collection: null` returns `None` for that field.

For collection details, assert each part preserves `release_date`, and add a helper or service test that a future date does not count toward released total while dates on/before today do.

- [ ] **Step 2: Verify RED**

Run:
```bash
python tests/standalone_v0341_smart_collections_behavior.py
```
Expected: FAIL because `tmdb_movie_details`/released filtering do not exist.

- [ ] **Step 3: Add `tmdb_movie_details()`**

Implement a single `/movie/{id}` request using the configured TMDb key, timeout 10 seconds, 404 => `None`, `raise_for_status()` otherwise. Normalize only fields needed by Homebuster. Do not call TV or Collection search endpoints from this helper.

- [ ] **Step 4: Preserve release dates in collection detail normalization**

Keep `tmdb_collection_details()` backward-compatible and retain its existing `parts` shape plus `release_date`. Do not create unowned Homebuster rows here.

- [ ] **Step 5: Re-run behavior test**

Run the v0.3.41 behavior script and expect PASS for integration normalization assertions.

- [ ] **Step 6: Commit if Git is available**

```bash
git add movie_catalogue/integrations.py tests/standalone_v0341_smart_collections_behavior.py
git commit -m "feat: expose tmdb collection membership metadata"
```

---

### Task 3: Build the Smart Collections service

**Files:**
- Create: `movie_catalogue/smart_collections.py`
- Expand: `tests/standalone_v0341_smart_collections_behavior.py`

**Interfaces:**
- Produces `cache_movie_collection_membership(db, tmdb_movie_id: int, relationship: dict | None) -> None`.
- Produces `backfill_uncached_movie_memberships(db, library_id: int, fetch_movie_details, limit: int = 8) -> dict`.
- Produces `refresh_known_collections(db, library_id: int, fetch_collection_details, now=None, limit: int = 2) -> dict`.
- Produces `get_smart_collection_suggestions(db, library_id: int, show_dismissed: bool = False, today=None) -> list[dict]`.
- Produces `approve_smart_collection(db, library_id: int, tmdb_collection_id: int) -> int`.
- Produces `dismiss_smart_collection(db, library_id: int, tmdb_collection_id: int) -> None`.
- Produces `restore_smart_collection(db, library_id: int, tmdb_collection_id: int) -> None`.
- Produces `auto_link_movie_to_approved_collection(db, movie_id: int) -> int | None`.
- Produces `ensure_organizational_collection_for_box_set(db, library_id: int, tmdb_collection_id: int, name: str, member_movie_ids: list[int]) -> int`.

- [ ] **Step 1: Write RED tests for cache semantics**

Create an in-memory SQLite fixture matching only required tables and assert:
- two physical copies sharing one `tmdb_id` need one cache row;
- checked-with-no-collection is represented by a row with null collection ID;
- `checked_at` updates when refreshed.

- [ ] **Step 2: Write RED tests for recommendation threshold**

Seed cache + movies so:
- 2/3 distinct owned => suggested;
- 2/4 => suggested;
- 2/9 => not suggested;
- 5/9 => suggested;
- duplicate physical copies do not increase owned count;
- TV rows are ignored;
- child box-set movie rows count as owned movies by TMDb ID.

Use cached official member IDs/totals from refreshed collection metadata. If the service needs a focused collection-details cache table to compute exact released IDs locally, add that schema in Task 1 before proceeding rather than storing only a total that cannot distinguish owned IDs correctly.

- [ ] **Step 3: Write RED tests for dismissal/restore/approval**

Assert:
- dismissed suggestions disappear by default;
- `show_dismissed=True` includes them with `dismissed=True`;
- restore makes them eligible again;
- approval creates one `collections` row with the TMDb ID and links all owned matching movie rows;
- approving twice reuses the same TMDb-backed collection;
- a manually named same-name collection without TMDb ID is not silently adopted.

- [ ] **Step 4: Write RED tests for auto-link and box-set sync**

Assert:
- newly owned matching movie auto-links to an already-approved TMDb collection;
- a physical box set explicitly identified as collection creates/reuses the TMDb-backed organizational collection regardless of threshold;
- only contained `movies` IDs are linked; parent `box_sets` row is never inserted into `movie_collections`.

- [ ] **Step 5: Write RED tests for bounded backfill and throttling**

Assert:
- backfill fetches at most 8 distinct uncached movie TMDb IDs per call;
- multiple copies cause one fetch;
- a fetch failure does not create a false checked cache row and does not raise out of the service batch;
- refresh fetches at most 2 stale known collection IDs per call;
- collection refreshed less than 24 hours ago is skipped;
- a failed refresh leaves the old cached detail usable and eligible for a later attempt.

- [ ] **Step 6: Implement the minimal service**

Keep SQL and policy in this module. Use transaction-neutral helpers where callers already own a transaction; helpers should not unexpectedly commit inside `create_box_set()` transactions. Recommended internal helpers:
```python
def _utc_now_text(now=None): ...
def _released_parts(details, today=None): ...
def _owned_tmdb_ids_for_collection(db, library_id, tmdb_collection_id): ...
def _get_or_create_tmdb_collection(db, library_id, tmdb_collection_id, name): ...
```

Persist collection details locally enough to compute the denominator without a network call. Prefer a focused table such as:
```sql
smart_collection_parts(
    tmdb_collection_id INTEGER NOT NULL,
    tmdb_movie_id INTEGER NOT NULL,
    title TEXT,
    release_date TEXT,
    PRIMARY KEY(tmdb_collection_id, tmdb_movie_id)
)
```
if exact released membership is required. If added, update Task 1 schema test and migration in the same implementation branch before marking Task 3 complete.

- [ ] **Step 7: Run behavior tests**

Run:
```bash
python tests/standalone_v0341_smart_collections_behavior.py
```
Expected: PASS.

- [ ] **Step 8: Commit if Git is available**

```bash
git add movie_catalogue/smart_collections.py movie_catalogue/db.py tests/standalone_v0341_smart_collections_behavior.py tests/standalone_v0341_smart_collections_schema_checks.py
git commit -m "feat: add smart collection recommendation service"
```

---

### Task 4: Add Collections-page recommendations, dismiss/restore, and bounded housekeeping

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/collections.html`
- Create: `tests/standalone_v0341_smart_collections_ui_checks.py`

**Interfaces:**
- GET `/libraries/<library_id>/collections?show_dismissed=1` renders suggestions and backfill status.
- POST `/libraries/<library_id>/smart-collections/<tmdb_collection_id>/approve`.
- POST `/libraries/<library_id>/smart-collections/<tmdb_collection_id>/dismiss`.
- POST `/libraries/<library_id>/smart-collections/<tmdb_collection_id>/restore`.
- Existing manual Collection POST remains unchanged.

- [ ] **Step 1: Write failing route/template source checks**

Assert the new route endpoint names, `show_dismissed`, `Create Collection`, `Not interested`, `Restore suggestion`, and a backfill-incomplete message/indicator exist. Assert all mutation forms contain CSRF tokens.

- [ ] **Step 2: Verify RED**

Run:
```bash
python tests/standalone_v0341_smart_collections_ui_checks.py
```
Expected: FAIL.

- [ ] **Step 3: Orchestrate bounded housekeeping on GET**

When Smart Collections are enabled, Collections GET should:
1. run one bounded uncached-membership backfill batch;
2. run one bounded stale-collection refresh batch;
3. compute suggestions locally;
4. render existing normal collections even if either network batch fails.

Catch `requests.RequestException`/service fetch failures at the boundary and log warnings; do not fail the page.

Expose status such as:
```python
smart_status = {
    "unchecked_movies": N,
    "processed_this_request": N,
    "refreshes_this_request": N,
}
```
The template should say recommendations may be incomplete while `unchecked_movies > 0`; do not claim completion prematurely.

- [ ] **Step 4: Add approve/dismiss/restore POST routes**

Require editor role. Each route calls the service, commits once, flashes a concise result, and redirects back preserving `show_dismissed=1` when relevant.

- [ ] **Step 5: Update `collections.html`**

Render Smart suggestions only when `library.smart_collections_enabled` is true. Show official name and exact `owned_count of released_count owned`. Dismissed rows should be visually labeled and offer Restore instead of Create/Not interested. Add one GET checkbox/toggle for Show dismissed collections; changing it may submit immediately, following the v0.3.40 checkbox pattern.

Do not alter the behavior of the existing manual Collection list/create/delete controls.

- [ ] **Step 6: Run UI/source checks and template parsing**

Run the v0.3.41 UI script, then parse all Jinja templates using the existing verification command/pattern used in prior releases.

- [ ] **Step 7: Commit if Git is available**

```bash
git add movie_catalogue/catalog.py movie_catalogue/templates/collections.html tests/standalone_v0341_smart_collections_ui_checks.py
git commit -m "feat: add smart collection recommendations UI"
```

---

### Task 5: Add per-library Smart Collections setting

**Files:**
- Modify: `movie_catalogue/libraries.py`
- Modify: `movie_catalogue/templates/library_settings.html`
- Expand: `tests/standalone_v0341_smart_collections_ui_checks.py`

**Interfaces:**
- POST `/libraries/<library_id>/settings/smart-collections`.
- Consumes `libraries.smart_collections_enabled` from Task 1.

- [ ] **Step 1: Add failing setting checks**

Assert owner-only route exists, checks checkbox presence, updates `smart_collections_enabled`, and settings template states that disabling hides recommendations/stops refresh without deleting existing collections.

- [ ] **Step 2: Verify RED**

Run the UI check script and expect failure on setting assertions.

- [ ] **Step 3: Implement route**

Use:
```python
enabled = 1 if request.form.get("smart_collections_enabled") else 0
db.execute("UPDATE libraries SET smart_collections_enabled=? WHERE id=?", (enabled, library_id))
```
Commit, flash, redirect to settings. Owner-only is preferred because this changes library behavior globally.

- [ ] **Step 4: Add settings panel**

Add a panel near Default content type / Box-set browsing with a checkbox labeled `Enable Smart Collections`. Explain the 50% + 2-movie suggestion behavior briefly and that existing approved collections remain if disabled.

- [ ] **Step 5: Re-run UI checks**

Expected: PASS for settings assertions.

- [ ] **Step 6: Commit if Git is available**

```bash
git add movie_catalogue/libraries.py movie_catalogue/templates/library_settings.html tests/standalone_v0341_smart_collections_ui_checks.py
git commit -m "feat: add smart collection library setting"
```

---

### Task 6: Wire automatic membership into movie identification and all physical box-set creation paths

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/box_set_service.py`
- Potentially modify: `movie_catalogue/mobile_api.py` only if the shared box-set service does not already cover Android creation
- Expand: `tests/standalone_v0341_smart_collections_behavior.py`
- Expand: `tests/standalone_v0341_smart_collections_ui_checks.py`

**Interfaces:**
- Consumes `auto_link_movie_to_approved_collection()` and `ensure_organizational_collection_for_box_set()` from Task 3.
- Shared box-set service must guarantee web and Android converge on the same behavior.

- [ ] **Step 1: Write failing source/behavior checks for box-set shared path**

Assert `create_box_set()` and `convert_movie_to_box_set()` synchronize contained member IDs into the organizational collection when `physical["tmdb_collection_id"]` exists. Verify web `box_sets.confirm_new_box_set` and Android `POST /api/v1/box-sets` still call the same shared service, so no duplicate API-specific collection logic is needed.

- [ ] **Step 2: Verify RED**

Run v0.3.41 behavior/UI scripts and expect failure.

- [ ] **Step 3: Integrate box-set synchronization transactionally**

Inside the existing transaction, after `reconcile_box_set_members()` returns member IDs, call:
```python
ensure_organizational_collection_for_box_set(
    db,
    library_id,
    int(physical["tmdb_collection_id"]),
    str(physical["title"]),
    member_ids,
)
```
Prefer the official TMDb collection name when already available to the caller/service; never infer identity from matching names.

- [ ] **Step 4: Wire movie identification/add metadata capture**

At each path where a movie obtains a canonical TMDb movie ID from a successful movie-detail/match response, cache its `belongs_to_collection` relationship when that response already contains it, then call `auto_link_movie_to_approved_collection()` after the movie row has the TMDb ID.

Where current search results do not contain `belongs_to_collection`, do **not** add a redundant detail call solely during every search. Allow bounded Collections-page backfill to fill missing cache entries later unless the path already loads details.

- [ ] **Step 5: Verify physical box-set behavior across web/Android source paths**

Run:
```bash
python tests/standalone_v0328_box_set_service_checks.py
python tests/standalone_v0328_collection_identify_review_checks.py
python tests/standalone_v0341_smart_collections_behavior.py
python tests/standalone_v0341_smart_collections_ui_checks.py
```
Expected: PASS.

- [ ] **Step 6: Commit if Git is available**

```bash
git add movie_catalogue/catalog.py movie_catalogue/box_set_service.py movie_catalogue/mobile_api.py tests/standalone_v0341_smart_collections_behavior.py tests/standalone_v0341_smart_collections_ui_checks.py
git commit -m "feat: auto-maintain tmdb backed collections"
```

---

### Task 7: Update HOMEBUSTER wordmark and release version

**Files:**
- Modify: `movie_catalogue/templates/base.html`
- Modify: `movie_catalogue/static/styles.css`
- Modify: `movie_catalogue/config.py`
- Modify: `README.md`
- Modify: `tests/standalone_v0340_shelf_toggle_branding_checks.py` if it hard-codes old casing/version assumptions
- Expand: `tests/standalone_v0341_smart_collections_ui_checks.py`
- Modify older standalone scripts that whitelist only through `0.3.40`.

**Interfaces:**
- Server reports v0.3.41.
- Header text renders literal `HOMEBUSTER`.

- [ ] **Step 1: Add failing branding/version checks**

Assert:
```text
<span class="brand-wordmark">HOMEBUSTER</span>
APP_VERSION = "0.3.41"
```
and CSS contains a yellow glow layer plus existing purple/block wordmark declarations. The test should reject a large fuzzy neon design by checking the glow radius remains small (for example <= 5px if using a parseable literal).

- [ ] **Step 2: Verify RED**

Run v0.3.41 UI check and expect failure.

- [ ] **Step 3: Update header/CSS**

Change only the film-strip header wordmark text. Keep login-page image untouched. Use a restrained layered shadow, for example:
```css
text-shadow:
  0 1px 0 rgba(57,20,82,.95),
  0 0 4px rgba(255,214,80,.38);
```
Retain purple foreground and block font family.

- [ ] **Step 4: Bump server version and README**

Set `APP_VERSION = "0.3.41"` and add a concise v0.3.41 README section covering Smart Collections, box-set organizational auto-linking, dismissals/settings, bounded TMDb housekeeping, and branding.

Update older standalone scripts whose accepted-version tuple ends at 0.3.40 so the full regression suite does not fail only because of the legitimate bump.

- [ ] **Step 5: Re-run branding/version checks**

Expected: PASS.

- [ ] **Step 6: Commit if Git is available**

```bash
git add movie_catalogue/templates/base.html movie_catalogue/static/styles.css movie_catalogue/config.py README.md tests
git commit -m "chore: release Homebuster 0.3.41"
```

---

### Task 8: Full regression, static verification, and release ZIP

**Files:**
- No feature code unless a failing regression identifies a real defect.
- Create final ZIP in `/mnt/data/` only after all available checks are complete.

**Interfaces:**
- Produces `Homebuster-v0.3.41-web-plus-android.zip`.

- [ ] **Step 1: Run every standalone regression script**

Run:
```bash
for f in tests/standalone_*.py; do echo "== $f =="; python "$f" || exit 1; done
```
Expected: all PASS.

- [ ] **Step 2: Compile Python source**

Run:
```bash
python -m compileall -q movie_catalogue tests
```
Expected: exit 0.

- [ ] **Step 3: Parse all Jinja templates**

Use Jinja2's parser against every file under `movie_catalogue/templates/`. Expected: all templates parse successfully.

- [ ] **Step 4: Validate static `url_for` endpoint references**

Run the same endpoint-reference scanner used for v0.3.40 and confirm zero missing endpoints. Include the new approve/dismiss/restore/settings routes.

- [ ] **Step 5: Run Android source checks without changing Android version**

From the Android source directory, run the existing `source-checks.py` and `url-regression-check.py` commands used in v0.3.40 verification. Expected: PASS. Do not claim an APK/Gradle build because this source package has no `gradlew` unless that fact changes.

- [ ] **Step 6: Scan for signing secrets**

Confirm the release tree contains no `.jks`, `.keystore`, or real `android/keystore.properties` file. Example:
```bash
find . -type f \( -name '*.jks' -o -name '*.keystore' -o -name 'keystore.properties' \) -print
```
Expected: no secret signing files.

- [ ] **Step 7: Attempt full pytest and report environment limitation accurately**

Run:
```bash
python -m pytest -q
```
If it still fails only because Flask is not installed, report exactly that; do not claim pytest passed. If Flask is available, require the suite to pass before release.

- [ ] **Step 8: Build the release ZIP**

From the parent directory, create:
```bash
zip -qr /mnt/data/Homebuster-v0.3.41-web-plus-android.zip Homebuster-v0.3.41
```
Use a clean v0.3.41 directory name inside the archive; exclude `__pycache__`, `.pyc`, local DBs, runtime backups, signing secrets, and other generated clutter.

- [ ] **Step 9: Verify ZIP integrity and SHA256**

Run:
```bash
unzip -t /mnt/data/Homebuster-v0.3.41-web-plus-android.zip
sha256sum /mnt/data/Homebuster-v0.3.41-web-plus-android.zip
```
Expected: archive integrity OK and a final SHA256 for the user.

- [ ] **Step 10: Final review against the spec**

Confirm every externally observable requirement in `docs/superpowers/specs/2026-09-14-smart-collections-design.md` is represented in code/tests, especially: 50% + 2 threshold, distinct TMDb ownership, movie-only scope, persistent dismissals/show-dismissed, library disable, no name-based identity, physical box-set auto-collection, future owned movie auto-link, 24-hour throttle, bounded backfill, silent failures, and no Android recommendation UI.

