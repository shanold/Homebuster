# Homebuster Android UI and Barcode Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Homebuster Android companion to visually match the Homebuster web application while improving barcode-derived TMDb searches without changing the raw product title shown to users.

**Architecture:** Keep Flask/SQLite as the system of record and keep Android as a native Compose companion. Add a focused server-side title sanitizer that produces TMDb search inputs separately from the raw barcode-provider title, then refactor Android styling into shared theme/components so all screens use the Homebuster web palette and card language consistently.

**Tech Stack:** Flask 3.1.2, SQLite, requests, pytest, Kotlin 2.3.21, Jetpack Compose/Material3, Retrofit 3.0.0, Coil 3.6.2, CameraX 1.6.2, ML Kit barcode scanning 17.3.0, Android API 37.

**Spec:** `docs/superpowers/specs/2026-09-10-android-ui-barcode-lookup-design.md`

## Global Constraints

- Preserve the existing Homebuster web UI and all existing browser behavior.
- Preserve existing `/api/v1` response fields; additions must be backwards-compatible.
- Barcode-provider API keys and TMDb API keys remain server-side only.
- Keep the raw barcode-provider title unchanged for display.
- Android targets SDK 37 and keeps Android 17 local-network permission behavior.
- Android system Back and visible Back controls must retain v0.3.5 behavior.
- Use Homebuster web colors: `#101218`, `#191d26`, `#222837`, `#30384a`, `#eef1f7`, `#9ca6b8`, `#7aa2ff`, `#345fc1`, `#ff6b6b`, `#62d49d`, `#f4c66b`.
- Bump server and Android app version together to `0.3.6`.

---

### Task 1: Add a testable barcode title sanitizer

**Files:**
- Modify: `movie_catalogue/integrations.py`
- Create: `tests/test_barcode_title_sanitizer.py`

**Interfaces:**
- Produces: `sanitize_barcode_movie_title(raw_title: str) -> tuple[str, int | None]`
- Consumed by: `barcode_product_lookup()` and `mobile_api.barcode_lookup()`

- [ ] **Step 1: Write failing sanitizer tests**

Create `tests/test_barcode_title_sanitizer.py`:

```python
from movie_catalogue.integrations import sanitize_barcode_movie_title


def test_strips_bracketed_dvd_and_extracts_year():
    assert sanitize_barcode_movie_title("Spider-Man [DVD] 2002") == ("Spider-Man", 2002)


def test_strips_parenthesized_bluray():
    assert sanitize_barcode_movie_title("Spider-Man (Blu-ray)") == ("Spider-Man", None)


def test_strips_4k_uhd_qualifier():
    assert sanitize_barcode_movie_title("Spider-Man 4K UHD") == ("Spider-Man", None)


def test_strips_ultra_hd_and_digital_copy():
    assert sanitize_barcode_movie_title("The Matrix Ultra HD + Digital Copy") == ("The Matrix", None)


def test_preserves_normal_movie_title():
    assert sanitize_barcode_movie_title("The DVD") == ("The DVD", None)


def test_normalizes_whitespace():
    assert sanitize_barcode_movie_title("  Spider-Man   [DVD]   ") == ("Spider-Man", None)
```

- [ ] **Step 2: Run the sanitizer tests and verify RED**

Run:

```bash
pytest -q tests/test_barcode_title_sanitizer.py
```

Expected: import failure because `sanitize_barcode_movie_title` does not exist.

- [ ] **Step 3: Implement the sanitizer**

In `movie_catalogue/integrations.py`, add:

```python
from datetime import datetime

_MEDIA_GROUP = r"(?:DVD|Blu[- ]?ray|4K(?:\s+UHD)?|UHD|Ultra\s+HD|Digital\s+Copy|Combo\s+Pack)"
_BRACKETED_MEDIA_RE = re.compile(rf"\s*[\[(]\s*{_MEDIA_GROUP}\s*[\])]\s*", re.I)
_TRAILING_MEDIA_RE = re.compile(
    rf"(?:\s*[-–:+]\s*|\s+)(?:{_MEDIA_GROUP})(?:\s*(?:\+|/|&)\s*(?:{_MEDIA_GROUP}))*\s*$",
    re.I,
)
_TRAILING_YEAR_RE = re.compile(r"(?:\s*[\[(]?\s*)((?:19|20)\d{2})(?:\s*[\])])?\s*$")


def sanitize_barcode_movie_title(raw_title: str) -> tuple[str, int | None]:
    original = re.sub(r"\s+", " ", (raw_title or "").strip())
    if not original:
        return "", None

    title = original
    year = None
    year_match = _TRAILING_YEAR_RE.search(title)
    if year_match:
        candidate = int(year_match.group(1))
        if 1900 <= candidate <= datetime.now().year + 1:
            year = candidate
            title = title[:year_match.start()].strip()

    title = _BRACKETED_MEDIA_RE.sub(" ", title)
    previous = None
    while title != previous:
        previous = title
        title = _TRAILING_MEDIA_RE.sub("", title).strip()

    title = re.sub(r"\s+", " ", title).strip(" -–:+")
    if not title:
        title = original
    return title, year
```

Then replace the existing one-line `clean = re.sub(...)` in `barcode_product_lookup()` with:

```python
clean, year = sanitize_barcode_movie_title(title)
```

and return both:

```python
"search_title": clean,
"search_year": year,
```

- [ ] **Step 4: Run sanitizer tests and verify GREEN**

Run:

```bash
pytest -q tests/test_barcode_title_sanitizer.py
```

Expected: all tests pass.

---

### Task 2: Support TMDb title + year search and fallback

**Files:**
- Modify: `movie_catalogue/integrations.py`
- Modify: `movie_catalogue/mobile_api.py`
- Create: `tests/test_barcode_api_lookup.py`

**Interfaces:**
- Modify: `tmdb_search(query: str, year: int | None = None)`
- API adds: `"lookup": {"title": str, "year": int | None}` to barcode product-match responses.

- [ ] **Step 1: Write failing API behavior tests**

Create `tests/test_barcode_api_lookup.py` with tests that monkeypatch `barcode_product_lookup` and `tmdb_search` in `movie_catalogue.mobile_api`:

```python
def test_barcode_lookup_preserves_raw_title_and_returns_clean_lookup(...):
    # product provider result:
    # {
    #   "product_title": "Spider-Man [DVD] 2002",
    #   "search_title": "Spider-Man",
    #   "search_year": 2002
    # }
    # Assert API product.product_title remains unchanged.
    # Assert API lookup == {"title": "Spider-Man", "year": 2002}.
    # Assert tmdb_search first receives ("Spider-Man", 2002).


def test_barcode_lookup_retries_without_year_when_first_search_empty(...):
    # tmdb_search returns [] for ("Spider-Man", 2002), then a result for ("Spider-Man", None).
    # Assert both calls occur in that order and second result is returned.
```

Use the existing app/test fixtures from the current `tests/` package for authenticated API requests rather than introducing a parallel app setup.

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
pytest -q tests/test_barcode_api_lookup.py
```

Expected: failures because `tmdb_search` does not accept `year` and barcode responses do not contain `lookup`.

- [ ] **Step 3: Extend TMDb search**

Change `tmdb_search` to:

```python
def tmdb_search(query: str, year: int | None = None):
    key = (current_app.config.get("TMDB_API_KEY") or "").strip()
    if not key:
        return []
    params = {"api_key": key, "query": query}
    if year is not None:
        params["year"] = year
    response = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params=params,
        timeout=10,
    )
    ...
```

Do not change the returned result structure.

- [ ] **Step 4: Add barcode lookup fallback**

In `mobile_api.barcode_lookup()`:

```python
search_title = (product.get("search_title") or product.get("product_title") or "").strip()
search_year = product.get("search_year")

try:
    matches = tmdb_search(search_title, search_year)
    if not matches and search_year is not None:
        matches = tmdb_search(search_title)
except Exception as exc:
    current_app.logger.warning("TMDb barcode match lookup failed: %s", exc)
    matches = []
```

Add to the JSON response:

```python
"lookup": {
    "title": search_title,
    "year": search_year,
},
```

Keep `product` and `tmdb_results` unchanged.

- [ ] **Step 5: Run barcode tests and the full Python suite**

Run:

```bash
pytest -q tests/test_barcode_title_sanitizer.py tests/test_barcode_api_lookup.py
pytest -q
```

Expected: all pass.

---

### Task 3: Add Homebuster Compose theme and shared components

**Files:**
- Create: `android/app/src/main/java/com/homebuster/mobile/HomebusterTheme.kt`
- Create: `android/app/src/main/java/com/homebuster/mobile/HomebusterComponents.kt`
- Modify: `android/app/src/main/java/com/homebuster/mobile/MainActivity.kt`

**Interfaces:**
- Produces composables: `HomebusterTheme`, `HomebusterTopBar`, `HomebusterScreenHeader`, `HomebusterPanel`, `HomebusterMovieCard`, `HomebusterMetaChip`, `HomebusterErrorCard`, `HomebusterEmptyState`.
- Consumed by all Android screens.

- [ ] **Step 1: Add source-level failing checks**

Create `android/source-checks.py` with assertions that:
- `MainActivity.kt` contains `HomebusterTheme`.
- `HomebusterTheme.kt` contains all required Homebuster hex colors.
- `HomebusterComponents.kt` defines `HomebusterMovieCard`, `HomebusterPanel`, and `HomebusterScreenHeader`.
- major screens call shared Homebuster components rather than raw `ListItem` for Collections/Loans.

Run:

```bash
python android/source-checks.py
```

Expected: fail because the new files/components do not exist.

- [ ] **Step 2: Create `HomebusterTheme.kt`**

Define `Color` constants matching the web CSS and a Material3 dark scheme:

```kotlin
val HbBackground = Color(0xFF101218)
val HbPanel = Color(0xFF191D26)
val HbPanel2 = Color(0xFF222837)
val HbText = Color(0xFFEEF1F7)
val HbMuted = Color(0xFF9CA6B8)
val HbLine = Color(0xFF30384A)
val HbAccent = Color(0xFF7AA2FF)
val HbPrimary = Color(0xFF345FC1)
val HbDanger = Color(0xFFFF6B6B)
val HbGood = Color(0xFF62D49D)
val HbWarning = Color(0xFFF4C66B)
```

Define `HomebusterTheme(content)` using `MaterialTheme(colorScheme=..., shapes=...)` with 14dp card corners and 8dp input/button corners.

- [ ] **Step 3: Create reusable components**

In `HomebusterComponents.kt` implement:
- branded top bar with Homebuster name and optional trailing action;
- screen header with arrow back button and title;
- bordered panel/card using `HbPanel`, `HbLine`, 14dp corners;
- small rounded metadata chip using `HbPanel2`;
- poster-first movie card with 2:3 image area, title, year/format metadata, border hover/press-safe styling;
- error and empty-state panels.

Keep components data-driven; they must not call the API.

- [ ] **Step 4: Apply the theme at the app root**

Change:

```kotlin
setContent { MaterialTheme(colorScheme = darkColorScheme()) { ... } }
```

to:

```kotlin
setContent { HomebusterTheme { HomebusterApp(SessionStore(this)) } }
```

- [ ] **Step 5: Run source checks**

Run:

```bash
python android/source-checks.py
```

Expected: checks related to theme/components pass; screen-specific checks may still fail until Task 4.

---

### Task 4: Redesign Login and Library screens

**Files:**
- Modify: `android/app/src/main/java/com/homebuster/mobile/MainActivity.kt`

**Interfaces:**
- Consumes shared components from Task 3.
- Does not change navigation enum or API contracts.

- [ ] **Step 1: Redesign Login**

Use a centered narrow panel visually equivalent to `.auth-card` from the web app:
- Homebuster branding/title.
- muted “Your movie library, in your pocket.”
- app version.
- local-network permission as a bordered inset panel.
- server/username/password fields with consistent spacing.
- full-width blue primary Sign In button.
- error shown with `HomebusterErrorCard`.

Keep `normalizeServerUrl`, permission flow, and `friendlyLogin` behavior unchanged.

- [ ] **Step 2: Redesign Library header/actions**

Use:
- `HomebusterTopBar` with app/server version and Log out.
- search input immediately beneath.
- three obvious actions: Collections, Loans, Scan Barcode.
- adaptive poster grid with `GridCells.Adaptive(155.dp)`.
- `HomebusterMovieCard` for each movie.
- useful empty state when there are no matching movies.

- [ ] **Step 3: Preserve existing library behavior**

Confirm:
- query still calls `/api/v1/movies?q=...`;
- selecting a poster still opens Details;
- Collections/Loans/Scanner navigation callbacks are unchanged;
- logout clears `SessionStore`.

- [ ] **Step 4: Run source checks**

Run:

```bash
python android/source-checks.py
```

Expected: Login/Library component assertions pass.

---

### Task 5: Redesign Details, Collections, Loans, Scanner, and Barcode Result

**Files:**
- Modify: `android/app/src/main/java/com/homebuster/mobile/MainActivity.kt`
- Modify: `android/app/src/main/java/com/homebuster/mobile/ScannerScreen.kt`
- Modify: `android/app/src/main/java/com/homebuster/mobile/Api.kt`

**Interfaces:**
- Add model:
```kotlin
data class BarcodeLookup(val title: String, val year: Int?)
```
- Extend `BarcodeResponse` with:
```kotlin
val lookup: BarcodeLookup?
```

- [ ] **Step 1: Extend barcode response model**

In `Api.kt`:

```kotlin
data class BarcodeLookup(val title: String, val year: Int?)

data class BarcodeResponse(
    val status: String,
    val upc: String?,
    val movie: Movie?,
    val product: BarcodeProduct?,
    val lookup: BarcodeLookup?,
    @SerializedName("tmdb_results") val tmdbResults: List<TmdbResult>?
)
```

Update the temporary loading constructor in `MainActivity.kt` to include `lookup = null`.

- [ ] **Step 2: Redesign Details**

Use:
- `HomebusterScreenHeader("Movie details", onBack)`;
- poster in a bordered 2:3 card;
- title as dominant text;
- year/format/runtime as chips;
- UPC in muted metadata if present;
- overview in a separate panel.

- [ ] **Step 3: Redesign Collections and Loans**

Replace raw Material `ListItem` rows with `HomebusterPanel` rows:
- Collections: name + muted movie count.
- Loans: movie title + borrower/returned status; active loans use warning/danger emphasis.

Keep endpoint calls unchanged.

- [ ] **Step 4: Redesign Scanner chrome**

Keep CameraX/ML Kit analysis untouched. Replace only the surrounding UI:
- Homebuster screen header/back arrow;
- concise scanner instruction;
- camera preview inside/under a dark panel;
- camera-permission denial shown via Homebuster error panel.

- [ ] **Step 5: Redesign Barcode Result and show raw vs cleaned lookup**

For an unknown-but-identified product display:
- raw provider title as the primary product title;
- UPC as muted text;
- “Searching TMDb for: Spider-Man (2002)” from `lookup`;
- count of TMDb candidates;
- if zero, explicit `No TMDb matches found`;
- candidate cards with poster/title/year when results exist.

For an owned barcode retain `You already own this` plus movie title/format.

- [ ] **Step 6: Verify Back behavior**

Ensure existing:

```kotlin
BackHandler(enabled = screen != Screen.LOGIN && screen != Screen.LIBRARY) { navigateBack() }
```

remains and all visible back arrows call `onBack`.

- [ ] **Step 7: Run Android source checks**

Run:

```bash
python android/source-checks.py
```

Expected: all checks pass.

---

### Task 6: Version bump, regression verification, and package

**Files:**
- Modify: `movie_catalogue/config.py`
- Modify: `android/app/build.gradle.kts`
- Modify: `README.md` if it contains the release version.
- Preserve: all existing browser templates and web CSS except version references if any.

**Interfaces:**
- Server `/api/v1/status` reports `0.3.6`.
- Android `BuildConfig.VERSION_NAME` reports `0.3.6`.

- [ ] **Step 1: Bump versions**

Set:

```python
APP_VERSION = "0.3.6"
```

and Android:

```kotlin
versionCode = 8
versionName = "0.3.6"
```

- [ ] **Step 2: Run full Python verification**

Run:

```bash
python -m compileall -q movie_catalogue app.py
pytest -q
```

Expected: exit 0.

- [ ] **Step 3: Run Android source verification**

Run:

```bash
python android/source-checks.py
```

Expected: exit 0.

- [ ] **Step 4: Run Android build when tooling exists**

Run from `android/`:

```bash
./gradlew assembleDebug
```

Expected: `BUILD SUCCESSFUL`.

If the runtime lacks Android SDK/Gradle dependencies, report that limitation explicitly and do not claim a successful APK compile.

- [ ] **Step 5: Verify web UI preservation**

Compare v0.3.5 and v0.3.6 web assets/templates:
- no template removed;
- `movie_catalogue/static/styles.css` unchanged;
- no browser route removed.

- [ ] **Step 6: Create source ZIP**

Create:

```text
Homebuster-v0.3.6-web-plus-android.zip
```

containing the complete server/web source, Android project, tests, spec, and plan.
