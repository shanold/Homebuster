# Library Default Content Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-library Movies/TV Shows/Movie Collections default that drives new matching and scanning operations without restricting library contents or rewriting existing inventory.

**Architecture:** Store one validated `libraries.default_media_type` value and let every fresh workflow derive its initial type from the library row. Explicit UI/API choices remain operation-scoped overrides, while already matched inventory continues using its stored item media type for refresh. Android consumes the server-provided library default rather than maintaining its own preference.

**Tech Stack:** Python 3, Flask, SQLite, Jinja2, vanilla JavaScript, Kotlin, Jetpack Compose, Retrofit/Gson.

**Spec:** `docs/superpowers/specs/2026-09-14-library-default-content-type-design.md`

## Global Constraints

- Target release is Homebuster `0.3.39`.
- Valid stored/API values are exactly `movie`, `tv`, and `collection`.
- Existing libraries migrate to `movie`.
- Changing a library default never mutates existing movies, box sets, TMDb identities, review state, or physical-copy metadata.
- A manual type choice applies only to the current operation/review continuation and is never persisted as a user/device override.
- Already matched item refresh uses the item's stored `media_type`.
- Never automatically fan out a lookup across Movie + TV + Collection endpoints.
- Android treats the server as authoritative for the library default.
- Existing clients remain compatible with the additive API field.

---

### Task 1: Persist and validate the library default

**Files:**
- Modify: `movie_catalogue/db.py`
- Modify: `movie_catalogue/libraries.py`
- Modify: `movie_catalogue/templates/library_new.html`
- Modify: `movie_catalogue/templates/library_settings.html`
- Test: `tests/standalone_v0339_library_default_schema_checks.py`

**Interfaces:**
- Produces: `libraries.default_media_type: str` with values `movie | tv | collection`.
- Produces: `normalize_library_default_media_type(value: object) -> str` in `movie_catalogue/libraries.py`.
- Consumes: existing `libraries` migration pattern in `movie_catalogue/db.py`.

- [ ] **Step 1: Write a failing standalone regression**

Create `tests/standalone_v0339_library_default_schema_checks.py` that opens the source files and asserts all of the following:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
db = (ROOT / "movie_catalogue/db.py").read_text()
libraries = (ROOT / "movie_catalogue/libraries.py").read_text()
new_html = (ROOT / "movie_catalogue/templates/library_new.html").read_text()
settings_html = (ROOT / "movie_catalogue/templates/library_settings.html").read_text()

assert "default_media_type" in db
assert "DEFAULT 'movie'" in db
assert "normalize_library_default_media_type" in libraries
assert '{"movie", "tv", "collection"}' in libraries
assert 'name="default_media_type"' in new_html
assert 'name="default_media_type"' in settings_html
```

- [ ] **Step 2: Run the regression and verify RED**

Run:
```bash
python tests/standalone_v0339_library_default_schema_checks.py
```
Expected: FAIL because `default_media_type` does not yet exist.

- [ ] **Step 3: Add the SQLite migration**

In the existing library-column migration block in `movie_catalogue/db.py`, add:
```python
if library_cols and "default_media_type" not in library_cols:
    db.execute(
        "ALTER TABLE libraries ADD COLUMN default_media_type TEXT NOT NULL DEFAULT 'movie'"
    )
```

Also include the column in the fresh `CREATE TABLE IF NOT EXISTS libraries` definition:
```sql
default_media_type TEXT NOT NULL DEFAULT 'movie'
```

Do not update any existing inventory rows.

- [ ] **Step 4: Add validation and creation persistence**

In `movie_catalogue/libraries.py`, add:
```python
LIBRARY_DEFAULT_MEDIA_TYPES = {"movie", "tv", "collection"}

def normalize_library_default_media_type(value):
    value = str(value or "movie").strip().lower()
    return value if value in LIBRARY_DEFAULT_MEDIA_TYPES else "movie"
```

Change library creation to read the form value and insert it:
```python
default_media_type = normalize_library_default_media_type(
    request.form.get("default_media_type")
)
cur = db.execute(
    "INSERT INTO libraries (name, owner_id, default_media_type) VALUES (?, ?, ?)",
    (name, current_user.id, default_media_type),
)
```

- [ ] **Step 5: Add create/settings selectors and settings endpoint**

In `library_new.html`, add a selector whose default is Movie:
```html
<label>Default content type
  <select name="default_media_type">
    <option value="movie" selected>Movies</option>
    <option value="tv">TV Shows</option>
    <option value="collection">Movie Collections / Box Sets</option>
  </select>
</label>
<p class="muted">Sets the default for adding, identifying, scanning, and matching. This does not restrict what the library can contain.</p>
```

In `library_settings.html`, add the same selector with `library.default_media_type` selected and explanatory copy that changing it does not alter existing inventory.

Add an owner-only POST endpoint in `libraries.py`, for example:
```python
@bp.post("/<int:library_id>/settings/default-media-type")
@login_required
@require_library_role("owner")
def set_default_media_type(library_id, library, role):
    default_media_type = normalize_library_default_media_type(
        request.form.get("default_media_type")
    )
    db = get_db()
    db.execute(
        "UPDATE libraries SET default_media_type=? WHERE id=?",
        (default_media_type, library_id),
    )
    db.commit()
    flash("Library default content type updated.", "success")
    return redirect(url_for("libraries.settings", library_id=library_id))
```

- [ ] **Step 6: Run the new regression**

Run:
```bash
python tests/standalone_v0339_library_default_schema_checks.py
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add movie_catalogue/db.py movie_catalogue/libraries.py movie_catalogue/templates/library_new.html movie_catalogue/templates/library_settings.html tests/standalone_v0339_library_default_schema_checks.py
git commit -m "feat: add library default content type"
```

---

### Task 2: Make fresh web matching flows use the library default

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/match_repair.html`
- Test: `tests/standalone_v0339_web_default_type_checks.py`

**Interfaces:**
- Consumes: `library["default_media_type"]`.
- Produces: fresh Identify/Match/Review initial type derived from the library.
- Preserves: explicit request/query/form type as an operation-scoped override.

- [ ] **Step 1: Write the failing web-default regression**

Create `tests/standalone_v0339_web_default_type_checks.py` and assert source contracts for:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / "movie_catalogue/catalog.py").read_text()
match_html = (ROOT / "movie_catalogue/templates/match_repair.html").read_text()

assert 'library["default_media_type"]' in catalog
assert "default_search_type" in catalog
assert "default_search_type" in match_html
assert 'value="movie"' in match_html
assert 'value="tv"' in match_html
assert 'value="collection"' in match_html
```

Also assert that the matched-refresh branch still derives refresh type from each movie's stored `media_type`, not from `bulk_search_type`.

- [ ] **Step 2: Verify RED**

Run:
```bash
python tests/standalone_v0339_web_default_type_checks.py
```
Expected: FAIL because fresh flows still hard-code/fall back to Movie or the unresolved row.

- [ ] **Step 3: Centralize the library fallback**

In `catalog.py`, add a small helper near `_identify_type`:
```python
def _library_default_type(library):
    return _identify_type(
        library["default_media_type"]
        if "default_media_type" in library.keys()
        else "movie"
    )
```

Use this helper only when there is no explicit operation type.

- [ ] **Step 4: Update fresh Identify**

For the GET branch of `identify_movie`, resolve:
```python
explicit_type = (request.args.get("media_type") or "").strip()
identify_type = _identify_type(explicit_type) if explicit_type else _library_default_type(library)
```

Keep the POST hidden/form `media_type` authoritative for completing the current operation. Preserve the existing contained-box-set guard.

Do not save `identify_type` back to `libraries`.

- [ ] **Step 5: Update Match / Repair page**

In `match_repair_page`, pass:
```python
default_search_type=_library_default_type(library)
```

In `match_repair.html`, mark the matching option selected from `default_search_type`. The JavaScript must continue sending `searchType.value` explicitly to every batch, so changing the selector affects that run only.

- [ ] **Step 6: Update fresh Mass Review**

In `match_repair_review`, resolve GET type as:
```python
explicit_type = (request.args.get("media_type") or "").strip()
identify_type = _identify_type(explicit_type) if explicit_type else _library_default_type(library)
```

When rendering an empty queue, pass `_library_default_type(library)` rather than hard-coded `"movie"`.

Preserve explicit `media_type` in Skip/Match/Dismiss redirects so a bulk-run override continues through its immediate review queue.

- [ ] **Step 7: Protect matched refresh behavior**

Review `match_repair_batch`. In the `refresh_matched` path, keep:
```python
stored_type = _media_type(movie["media_type"] or "movie")
```
(or the existing equivalent) as the endpoint selector for already matched rows. `bulk_search_type` must govern only unresolved matching.

- [ ] **Step 8: Run the web regression and existing match/review regressions**

Run:
```bash
python tests/standalone_v0339_web_default_type_checks.py
python tests/standalone_v0331_import_hub_bulk_type_checks.py
python tests/standalone_v0326_identify_tv_type_checks.py
python tests/standalone_v0323_review_queue_checks.py
```
If an older filename differs, run the corresponding existing v0.3.23/v0.3.26/v0.3.31 standalone scripts present in `tests/`.

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add movie_catalogue/catalog.py movie_catalogue/templates/match_repair.html tests/standalone_v0339_web_default_type_checks.py
git commit -m "feat: default web matching to library type"
```

---

### Task 3: Expose the preference through the mobile API

**Files:**
- Modify: `movie_catalogue/mobile_api.py`
- Test: `tests/standalone_v0339_mobile_library_default_checks.py`
- Test: `tests/test_mobile_api.py`

**Interfaces:**
- Produces: `GET /api/v1/libraries` objects with `id`, `name`, `role`, `default_media_type`.
- Preserves: existing barcode/TMDb `media_type` query parameter behavior.

- [ ] **Step 1: Write a failing API source regression**

Create `tests/standalone_v0339_mobile_library_default_checks.py`:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / "movie_catalogue/mobile_api.py").read_text()

assert "default_media_type" in api
assert "SELECT l.id, l.name, l.default_media_type" in api
assert 'request.args.get("media_type")' in api
```

- [ ] **Step 2: Verify RED**

Run:
```bash
python tests/standalone_v0339_mobile_library_default_checks.py
```
Expected: FAIL because the libraries endpoint currently returns only id/name/role.

- [ ] **Step 3: Extend the libraries endpoint**

Update both sides of the existing UNION in `GET /api/v1/libraries`:
```sql
SELECT l.id, l.name, l.default_media_type, 'owner' AS role
...
SELECT l.id, l.name, l.default_media_type, lm.role
```

Do not change the barcode endpoint's explicit `media_type` contract.

- [ ] **Step 4: Add/extend Flask API behavior test**

In `tests/test_mobile_api.py`, add a test that creates or updates a library to `tv`, calls `/api/v1/libraries`, and asserts:
```python
assert body["libraries"][0]["default_media_type"] == "tv"
```

Also assert existing fields remain present.

- [ ] **Step 5: Run API tests where dependencies are available**

Run:
```bash
python tests/standalone_v0339_mobile_library_default_checks.py
python -m pytest tests/test_mobile_api.py -q
```

Expected: standalone PASS. Pytest PASS in a Flask-equipped environment; if Flask is absent in the packaging environment, record that dependency limitation rather than claiming pytest passed.

- [ ] **Step 6: Commit**

```bash
git add movie_catalogue/mobile_api.py tests/standalone_v0339_mobile_library_default_checks.py tests/test_mobile_api.py
git commit -m "feat: expose library default type in mobile API"
```

---

### Task 4: Make Android scanning start from the active library default

**Files:**
- Modify: `android/app/src/main/java/com/homebuster/mobile/Api.kt`
- Modify: `android/app/src/main/java/com/homebuster/mobile/MainActivity.kt`
- Test: `tests/standalone_v0339_android_scanner_default_checks.py`

**Interfaces:**
- Consumes: API `Library.defaultMediaType`.
- Produces: barcode-result initial `mediaType` equal to the active library default.
- Preserves: user selection as an in-screen one-operation override.

- [ ] **Step 1: Write a failing Android source regression**

Create `tests/standalone_v0339_android_scanner_default_checks.py` asserting:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / "android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
main = (ROOT / "android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()

assert "data class Library" in api
assert '@SerializedName("default_media_type")' in api
assert 'val defaultMediaType: String = "movie"' in api
assert "libraryId" in main
assert "defaultMediaType" in main
assert "initialMediaType" in main
```

- [ ] **Step 2: Verify RED**

Run:
```bash
python tests/standalone_v0339_android_scanner_default_checks.py
```
Expected: FAIL because Android currently has no Library model/default field and barcode result hard-codes `mediaType = "movie"`.

- [ ] **Step 3: Model and fetch libraries**

In `Api.kt`, add:
```kotlin
data class Library(
    val id: Int,
    val name: String,
    val role: String,
    @SerializedName("default_media_type")
    val defaultMediaType: String = "movie"
)

data class LibrariesResponse(val libraries: List<Library>)
```

Add to `HomebusterApi`:
```kotlin
@GET("api/v1/libraries")
suspend fun libraries(
    @Header("Authorization") auth: String
): LibrariesResponse
```

The Kotlin default preserves compatibility with an older server that omits the field.

- [ ] **Step 4: Track the active library**

The current Android UI aggregates accessible movies, so add the smallest explicit active-library state needed for scanner intent rather than silently guessing forever.

In `HomebusterApp`, load accessible libraries after login/session restoration, retain:
```kotlin
var libraries by remember { mutableStateOf<List<Library>>(emptyList()) }
var activeLibrary by remember { mutableStateOf<Library?>(null) }
```

Choose the first accessible library only as the initial active library, matching current first-library fallback behavior elsewhere. If the existing Android library screen already has a library selector by implementation time, bind `activeLibrary` to that selection instead.

Pass `activeLibrary` into the scan/barcode-result flow.

- [ ] **Step 5: Initialize each scan from the library default**

Change the barcode-result composable signature to accept:
```kotlin
initialMediaType: String
```

Initialize:
```kotlin
var mediaType by remember(upc, initialMediaType) {
    mutableStateOf(
        initialMediaType.takeIf { it in setOf("movie", "tv", "collection") } ?: "movie"
    )
}
```

Call it with:
```kotlin
initialMediaType = activeLibrary?.defaultMediaType ?: "movie"
```

The existing Movie/TV/Collection buttons continue updating only the local `mediaType` state. Because the state is keyed by `upc` and `initialMediaType`, a new scan returns to the library default rather than remembering the prior exception.

Ensure add requests use the active library id instead of relying on an unrelated global fallback where applicable.

- [ ] **Step 6: Run Android source checks**

Run:
```bash
python tests/standalone_v0339_android_scanner_default_checks.py
python tests/standalone_android_source_checks.py
python tests/standalone_android_url_regression.py
```
Use the actual existing Android standalone filenames if they differ.

Expected: PASS.

- [ ] **Step 7: Build Android when the SDK/toolchain is available**

Run:
```bash
cd android
./gradlew test assembleDebug
```

Expected: PASS in an Android-build-equipped environment. If the environment cannot build Android, report source-check status only and do not claim an APK build.

- [ ] **Step 8: Commit**

```bash
git add android/app/src/main/java/com/homebuster/mobile/Api.kt android/app/src/main/java/com/homebuster/mobile/MainActivity.kt tests/standalone_v0339_android_scanner_default_checks.py
git commit -m "feat: default Android scanner to library type"
```

---

### Task 5: Version, documentation, compatibility, and release verification

**Files:**
- Modify: `movie_catalogue/__init__.py`
- Modify: `README.md`
- Modify: older standalone version-contract tests as required
- Verify: all `tests/standalone_*.py`

**Interfaces:**
- Produces: Homebuster v0.3.39 source ZIP.
- Preserves: no signing secrets in distributable source.

- [ ] **Step 1: Add v0.3.39 to version contracts**

Update `APP_VERSION` to:
```python
APP_VERSION = "0.3.39"
```

Extend only the existing standalone version allowlists that intentionally enumerate supported releases.

- [ ] **Step 2: Document the feature**

Add a README release note explaining:
```text
Libraries now have a default content type: Movies, TV Shows, or Movie Collections / Box Sets.
The setting controls the initial choice for new Add/Identify/Match/Android scan operations only.
It never restricts library contents or changes existing inventory.
```

- [ ] **Step 3: Run every standalone regression**

Run:
```bash
set -e
for test in tests/standalone_*.py; do
  echo "==> $test"
  python "$test"
done
```

Expected: every script exits 0.

- [ ] **Step 4: Compile Python**

Run:
```bash
python -m compileall -q movie_catalogue tests
```
Expected: exit 0.

- [ ] **Step 5: Parse every Jinja template**

Run the repository's existing Jinja parse verification. If no script exists, use:
```bash
python - <<'PY'
from pathlib import Path
from jinja2 import Environment
env = Environment()
for path in Path("movie_catalogue/templates").glob("*.html"):
    env.parse(path.read_text())
print("Jinja templates parsed")
PY
```
Expected: exit 0.

- [ ] **Step 6: Run static route-reference verification**

Run the existing Homebuster `url_for`/endpoint source checker used in prior releases and require zero missing endpoint references.

- [ ] **Step 7: Attempt Flask tests**

Run:
```bash
python -m pytest -q
```
Expected in a fully provisioned environment: PASS. If Flask is not installed, report the exact dependency failure and do not describe pytest as passing.

- [ ] **Step 8: Verify Android source/build status**

Run the existing Android source and URL regressions. If Gradle/Android SDK is available, run:
```bash
cd android
./gradlew test assembleDebug
```
Do not claim an Android APK/build passed unless this command actually succeeds.

- [ ] **Step 9: Scan for signing secrets**

Before packaging, verify the source tree contains none of:
```text
*.jks
*.keystore
android/keystore.properties
```
and no literal release signing passwords.

- [ ] **Step 10: Package and verify**

From the directory containing the source root:
```bash
zip -qr Homebuster-v0.3.39-web-plus-android.zip Homebuster-v0.3.39
unzip -t Homebuster-v0.3.39-web-plus-android.zip
sha256sum Homebuster-v0.3.39-web-plus-android.zip
```

Expected: ZIP integrity reports no errors and SHA-256 is recorded in the release response.

- [ ] **Step 11: Final requirements review**

Re-read `docs/superpowers/specs/2026-09-14-library-default-content-type-design.md` and confirm each acceptance criterion against either a test or inspected implementation before declaring v0.3.39 complete.
