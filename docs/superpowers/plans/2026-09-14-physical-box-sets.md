# Physical Movie Box Sets / TMDb Collections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class physical movie box sets that can be populated from TMDb Collections, appear as one physical inventory item by default, expose contained films for browsing/search, and support whole-set or per-film loans.

**Architecture:** Keep existing `movies` rows as standalone physical copies and add dedicated `box_sets`, `box_set_members`, and loan tables. A focused `box_set_service.py` owns shared box-set queries/state rules, `box_sets.py` owns web routes, existing catalogue/search settings merge box-set cards and optional virtual member cards, and the mobile API exposes the same first-class objects without requiring Android UI changes in this release.

**Tech Stack:** Python 3, Flask, SQLite, Jinja, requests/TMDb API, pytest/standalone source checks, existing Kotlin/Compose Android source contract only.

**Spec:** `docs/superpowers/specs/2026-09-14-physical-box-sets-design.md`

## Global Constraints

- Existing `movies`, `loans`, `collections`, and `movie_collections` semantics remain unchanged.
- Existing libraries default to `show_box_set_members = 0` and therefore keep the current physical-only grid behavior until a box set is added.
- A box set is one physical item; contained films are not standalone physical copies and do not receive their own barcode or shelf.
- Whole-set loans and member-film loans are mutually exclusive while active.
- Disc-to-film mapping is intentionally not modeled.
- Existing user-created Homebuster Collections remain separate from TMDb Collections / Movie Box Sets.
- TMDb Movie, TV, and Collection endpoints are queried only when that mode is explicitly selected or strongly preselected by the parser; never fan out to all three endpoints.
- Movie CSV behavior must remain backward compatible; box sets use a separate CSV import/export format in this release.
- Web/server behavior is stabilized first. Android UI work is deferred; only API/source contracts needed for a later Android client are added now.
- Preserve external Android release signing behavior; do not add `.jks`, `.keystore`, or real `keystore.properties` files to the source package.

---

## File Structure

**Create**
- `movie_catalogue/box_set_service.py` — shared data access, effective availability, creation/update helpers, and loan rule enforcement for box sets.
- `movie_catalogue/box_sets.py` — web blueprint for box-set search, confirmation, detail/edit, member management, loans, deletion, and box-set CSV routes.
- `movie_catalogue/templates/box_set_lookup.html` — explicit TMDb Collection search screen.
- `movie_catalogue/templates/box_set_confirm.html` — TMDb collection confirmation/member checklist and physical metadata form.
- `movie_catalogue/templates/box_set_detail.html` — physical metadata, members, loan state, history, edit/delete actions.
- `movie_catalogue/templates/box_set_edit.html` — edit physical metadata and shelf.
- `tests/test_box_set_migration.py` — additive schema/default migration tests.
- `tests/test_box_set_tmdb.py` — collection-only endpoint/search/detail mapping tests.
- `tests/test_box_set_web.py` — create/detail/search/grid/settings/member-management behavior.
- `tests/test_box_set_loans.py` — whole-set/member mutual-exclusion and return behavior.
- `tests/test_box_set_csv.py` — dedicated box-set CSV round trip and movie CSV regression.
- `tests/test_box_set_api.py` — first-class API list/detail/create/search/loan contract tests.
- `tests/standalone_v0327_box_set_parser_checks.py` — parser/source checks that can run without Flask dependencies.

**Modify**
- `movie_catalogue/db.py` — additive tables, indexes, and `libraries.show_box_set_members` migration.
- `movie_catalogue/__init__.py` — register the new `box_sets` blueprint.
- `movie_catalogue/integrations.py` — TMDb collection search/details helpers.
- `movie_catalogue/barcode_parser.py` — conservative box-set hint/candidate extraction.
- `movie_catalogue/catalog.py` — merge box-set cards/member virtual cards into library browsing/search/counts while preserving movie routes.
- `movie_catalogue/libraries.py` — save the per-library expanded-member setting and include box-set counts in destructive operations.
- `movie_catalogue/mobile_api.py` — first-class box-set and TMDb collection endpoints; collection-aware barcode lookup mode.
- `movie_catalogue/templates/movie_lookup.html` — add explicit Movie Collection / Box Set choice and route it to box-set lookup.
- `movie_catalogue/templates/catalogue.html` — render standalone movies, box sets, and optional member virtual cards distinctly.
- `movie_catalogue/templates/library_settings.html` — checkbox for showing contained films in the main grid.
- `movie_catalogue/templates/loans.html` — render active standalone, whole-box-set, and member-film loans together.
- `movie_catalogue/static/styles.css` — box-set/member badges, contained-film list, incomplete/loan states.
- `API.md` — document box-set and collection lookup endpoints.
- `README.md` — v0.3.27 feature notes and box-set behavior.
- `movie_catalogue/config.py` — bump server version after implementation verification.

---

### Task 1: Additive box-set database schema

**Files:**
- Modify: `movie_catalogue/db.py`
- Test: `tests/test_box_set_migration.py`

**Interfaces:**
- Produces tables `box_sets`, `box_set_members`, `box_set_loans`, `box_set_member_loans`.
- Produces library column `show_box_set_members INTEGER NOT NULL DEFAULT 0`.
- Later tasks rely on foreign keys, indexes, and one-active-loan partial indexes defined here.

- [ ] **Step 1: Write migration tests for a fresh and existing v0.3.26 database**

```python
import sqlite3


def test_box_set_schema_is_added_to_existing_database(app):
    from movie_catalogue.db import get_db, table_columns
    with app.app_context():
        db = get_db()
        assert "show_box_set_members" in table_columns(db, "libraries")
        library = db.execute("SELECT show_box_set_members FROM libraries LIMIT 1").fetchone()
        if library:
            assert library["show_box_set_members"] == 0
        for name in ("box_sets", "box_set_members", "box_set_loans", "box_set_member_loans"):
            assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()


def test_box_set_member_identity_is_unique_per_box_set(app):
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        owner = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not owner:
            return
        library_id = db.execute("SELECT id FROM libraries LIMIT 1").fetchone()["id"]
        box_id = db.execute("INSERT INTO box_sets (library_id,title) VALUES (?,?)", (library_id, "Test Set")).lastrowid
        db.execute("INSERT INTO box_set_members (box_set_id,tmdb_id,title,position) VALUES (?,?,?,?)", (box_id, 1, "Film", 0))
        with __import__("pytest").raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO box_set_members (box_set_id,tmdb_id,title,position) VALUES (?,?,?,?)", (box_id, 1, "Film", 1))
```

- [ ] **Step 2: Run the migration tests and verify they fail because the schema does not exist**

Run: `pytest tests/test_box_set_migration.py -v`

Expected: FAIL for missing `show_box_set_members` / missing box-set tables.

- [ ] **Step 3: Add the new schema to `_create_catalog_tables()` and additive library migration**

Use these exact table responsibilities:

```sql
CREATE TABLE IF NOT EXISTS box_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL,
    barcode TEXT,
    title TEXT NOT NULL,
    tmdb_collection_id INTEGER,
    poster_path TEXT,
    format TEXT,
    version TEXT,
    country TEXT,
    language TEXT,
    region TEXT,
    disc_count INTEGER,
    notes TEXT,
    shelf_id INTEGER,
    status TEXT NOT NULL DEFAULT 'owned',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
    FOREIGN KEY(shelf_id) REFERENCES shelves(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_box_sets_library_title ON box_sets(library_id, title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_box_sets_barcode ON box_sets(library_id, barcode);
CREATE INDEX IF NOT EXISTS idx_box_sets_tmdb_collection ON box_sets(library_id, tmdb_collection_id);

CREATE TABLE IF NOT EXISTS box_set_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_set_id INTEGER NOT NULL,
    tmdb_id INTEGER,
    title TEXT NOT NULL,
    year TEXT,
    poster_path TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(box_set_id) REFERENCES box_sets(id) ON DELETE CASCADE,
    UNIQUE(box_set_id, tmdb_id)
);
CREATE INDEX IF NOT EXISTS idx_box_set_members_box ON box_set_members(box_set_id, position, id);
CREATE INDEX IF NOT EXISTS idx_box_set_members_title ON box_set_members(title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS box_set_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL,
    box_set_id INTEGER NOT NULL,
    borrower_name TEXT NOT NULL,
    phone TEXT,
    loaned_date TEXT NOT NULL,
    returned_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
    FOREIGN KEY(box_set_id) REFERENCES box_sets(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_loan_per_box_set
    ON box_set_loans(box_set_id) WHERE returned_date IS NULL;

CREATE TABLE IF NOT EXISTS box_set_member_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL,
    box_set_member_id INTEGER NOT NULL,
    borrower_name TEXT NOT NULL,
    phone TEXT,
    loaned_date TEXT NOT NULL,
    returned_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
    FOREIGN KEY(box_set_member_id) REFERENCES box_set_members(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_loan_per_box_member
    ON box_set_member_loans(box_set_member_id) WHERE returned_date IS NULL;
```

Extend `_ensure_catalog_columns(db)` with:

```python
library_cols = table_columns(db, "libraries")
if library_cols and "show_box_set_members" not in library_cols:
    db.execute("ALTER TABLE libraries ADD COLUMN show_box_set_members INTEGER NOT NULL DEFAULT 0")
```

- [ ] **Step 4: Run migration and legacy migration regressions**

Run: `pytest tests/test_box_set_migration.py tests/test_migration.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the schema task**

```bash
git add movie_catalogue/db.py tests/test_box_set_migration.py
git commit -m "feat: add physical box set schema"
```

---

### Task 2: Add TMDb Collection integration and deterministic member mapping

**Files:**
- Modify: `movie_catalogue/integrations.py`
- Create: `tests/test_box_set_tmdb.py`

**Interfaces:**
- Produces `tmdb_collection_search(query: str) -> list[dict]`.
- Produces `tmdb_collection_details(collection_id: int) -> dict | None`.
- Result normalization uses `id`, `title`, `overview`, `poster_path`, and ordered `parts` where each part has `id`, `title`, `release_date`, `poster_path`, `position`.

- [ ] **Step 1: Write tests proving Collection mode hits only Collection endpoints**

```python
def test_collection_search_uses_only_search_collection(monkeypatch, app):
    from movie_catalogue import integrations
    calls = []

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"id": 1241, "name": "Harry Potter Collection", "poster_path": "/hp.jpg"}]}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return Response()

    monkeypatch.setattr(integrations.requests, "get", fake_get)
    with app.app_context():
        app.config["TMDB_API_KEY"] = "test"
        results = integrations.tmdb_collection_search("Harry Potter")
    assert results[0]["title"] == "Harry Potter Collection"
    assert len(calls) == 1
    assert calls[0][0].endswith("/search/collection")


def test_collection_details_preserve_tmdb_part_order(monkeypatch, app):
    from movie_catalogue import integrations
    # fake response parts deliberately ordered 3,1,2 and assert returned positions are 0,1,2 in response order
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest tests/test_box_set_tmdb.py -v`

Expected: FAIL because the new helpers do not exist.

- [ ] **Step 3: Implement collection search/details without changing Movie/TV helpers**

Add constants/local request logic parallel to `tmdb_search`:

```python
def tmdb_collection_search(query: str):
    # GET https://api.themoviedb.org/3/search/collection with api_key + query
    # normalize `name` to `title`; return [] when key/query is absent


def tmdb_collection_details(collection_id: int):
    # GET https://api.themoviedb.org/3/collection/{id}
    # normalize each `parts` item and attach deterministic `position`
```

Do not call `tmdb_search()` from either helper.

- [ ] **Step 4: Run collection and existing TV/movie integration tests**

Run: `pytest tests/test_box_set_tmdb.py tests/test_mobile_api.py tests/test_catalog_features.py -v`

Expected: PASS except for any environment-known dependency limitation; if Flask is unavailable, run the standalone source checks and record that limitation rather than claiming pytest passed.

- [ ] **Step 5: Commit TMDb Collection support**

```bash
git add movie_catalogue/integrations.py tests/test_box_set_tmdb.py
git commit -m "feat: add TMDb collection lookup"
```

---

### Task 3: Add conservative box-set title detection and search candidates

**Files:**
- Modify: `movie_catalogue/barcode_parser.py`
- Create: `tests/standalone_v0327_box_set_parser_checks.py`

**Interfaces:**
- Produces `detect_movie_box_set_hint(raw_title: str) -> bool`.
- Produces `movie_box_set_title_candidates(raw_title: str) -> list[str]`.
- Strong suffixes include collection/box set/film-count/trilogy/quadrilogy/complete-movie-collection wording.
- Must not reinterpret ordinary titles such as `The Collection` as a box set without additional retail/set evidence.

- [ ] **Step 1: Write standalone parser regression cases**

```python
from movie_catalogue.barcode_parser import detect_movie_box_set_hint, movie_box_set_title_candidates

cases = {
    "Harry Potter 8-Film Collection Blu-ray": "Harry Potter",
    "The Lord of the Rings Trilogy 4K UHD": "The Lord of the Rings",
    "Alien Quadrilogy DVD Box Set": "Alien",
    "Back to the Future Complete Movie Collection Blu-ray": "Back to the Future",
}
for raw, expected in cases.items():
    assert detect_movie_box_set_hint(raw)
    assert movie_box_set_title_candidates(raw)[0] == expected

assert not detect_movie_box_set_hint("The Collection")
assert movie_box_set_title_candidates("The Collection")[0] == "The Collection"
```

- [ ] **Step 2: Run standalone check and verify RED**

Run: `python tests/standalone_v0327_box_set_parser_checks.py`

Expected: FAIL because the functions do not exist.

- [ ] **Step 3: Implement set-hint stripping on top of existing copy-metadata cleanup**

Detection must be conservative. Use explicit patterns such as:

```python
r"\b\d+\s*[- ]?film\s+collection\b"
r"\b(?:complete\s+)?movie\s+collection\b"
r"\bbox\s*set\b"
r"\btrilogy\b"
r"\bquadrilogy\b"
```

For bare `collection`, require additional copy/set evidence (film count, format, `complete`, `box set`) so `The Collection` stays an ordinary movie title.

- [ ] **Step 4: Run all parser regressions**

Run:

```bash
python tests/standalone_barcode_parser_checks.py
python tests/standalone_v0317_identify_parser_checks.py
python tests/standalone_v0318_smart_matching_checks.py
python tests/standalone_v0319_metadata_repair_checks.py
python tests/standalone_v0320_scanner_shared_pipeline_checks.py
python tests/standalone_v0325_tv_set_parser_checks.py
python tests/standalone_v0327_box_set_parser_checks.py
```

Expected: all PASS.

- [ ] **Step 5: Commit parser support**

```bash
git add movie_catalogue/barcode_parser.py tests/standalone_v0327_box_set_parser_checks.py
git commit -m "feat: detect movie box set titles"
```

---

### Task 4: Create shared box-set service and transactional creation

**Files:**
- Create: `movie_catalogue/box_set_service.py`
- Test: `tests/test_box_set_web.py`

**Interfaces:**
- Produces `get_box_set(db, library_id: int, box_set_id: int)`.
- Produces `get_box_set_members(db, box_set_id: int) -> list`.
- Produces `create_box_set(db, library_id: int, physical: dict, members: list[dict]) -> int`.
- Produces `box_set_effective_state(db, box_set_id: int) -> dict` with `whole_loan`, `member_loans`, `incomplete`, `can_loan_whole`.
- Produces `member_effective_state(db, member_id: int) -> dict` with `state in {available, loaned_individually, loaned_with_box_set}`.

- [ ] **Step 1: Write a failing transactional creation test**

```python
def test_create_box_set_creates_one_physical_row_and_selected_members(app):
    from movie_catalogue.box_set_service import create_box_set
    from movie_catalogue.db import get_db
    with app.app_context():
        db = get_db()
        library_id = db.execute("SELECT id FROM libraries LIMIT 1").fetchone()["id"]
        box_id = create_box_set(db, library_id, {
            "title": "Harry Potter 8-Film Collection",
            "tmdb_collection_id": 1241,
            "format": "Blu-ray",
        }, [
            {"tmdb_id": 671, "title": "Harry Potter and the Philosopher's Stone", "year": "2001", "poster_path": "/1.jpg", "position": 0},
            {"tmdb_id": 672, "title": "Harry Potter and the Chamber of Secrets", "year": "2002", "poster_path": "/2.jpg", "position": 1},
        ])
        assert db.execute("SELECT COUNT(*) FROM box_sets WHERE id=?", (box_id,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM box_set_members WHERE box_set_id=?", (box_id,)).fetchone()[0] == 2
```

Also add a failure test that injects a duplicate selected member and proves no half-created `box_sets` row remains after rollback.

- [ ] **Step 2: Run the test and verify RED**

Run: `pytest tests/test_box_set_web.py::test_create_box_set_creates_one_physical_row_and_selected_members -v`

Expected: FAIL because `box_set_service` does not exist.

- [ ] **Step 3: Implement service functions with one transaction boundary**

`create_box_set()` must use `with db:` or explicit savepoint/rollback so the parent/member insert succeeds or fails as one unit. Normalize only the fields defined in the spec; do not copy barcode/shelf into members.

- [ ] **Step 4: Run service creation tests**

Run: `pytest tests/test_box_set_web.py -k "create_box_set or transaction" -v`

Expected: PASS.

- [ ] **Step 5: Commit the service layer**

```bash
git add movie_catalogue/box_set_service.py tests/test_box_set_web.py
git commit -m "feat: add box set service layer"
```

---

### Task 5: Build web Add → Collection / Box Set lookup and confirmation flow

**Files:**
- Create: `movie_catalogue/box_sets.py`
- Create: `movie_catalogue/templates/box_set_lookup.html`
- Create: `movie_catalogue/templates/box_set_confirm.html`
- Modify: `movie_catalogue/__init__.py`
- Modify: `movie_catalogue/templates/movie_lookup.html`
- Modify: `movie_catalogue/static/styles.css`
- Test: `tests/test_box_set_web.py`

**Interfaces:**
- Web routes:
  - `GET /libraries/<library_id>/box-sets/new?q=...`
  - `GET|POST /libraries/<library_id>/box-sets/new/confirm?tmdb_collection_id=...`
- Uses `tmdb_collection_search`, `tmdb_collection_details`, `create_box_set`.
- POST member selection uses repeated `member_tmdb_id` values and validates chosen IDs against freshly fetched TMDb collection details rather than trusting client titles/posters.

- [ ] **Step 1: Write failing web-flow tests**

Test these exact behaviors:

```python
def test_add_title_offers_collection_mode(client, app):
    # GET /movies/new and assert "Movie Collection / Box Set" exists.


def test_collection_lookup_does_not_call_movie_or_tv_search(client, app, monkeypatch):
    # patch integrations.tmdb_collection_search and catalog movie/tv search separately;
    # GET /box-sets/new?q=Harry+Potter; assert collection helper called once and movie helper zero times.


def test_collection_confirmation_selects_all_parts_by_default(client, app, monkeypatch):
    # fake collection details with 3 parts; assert all 3 checkbox values render checked.


def test_collection_save_can_exclude_a_tmdb_part(client, app, monkeypatch):
    # POST selected IDs for two of three parts; assert only two members stored.
```

- [ ] **Step 2: Run the flow tests and verify RED**

Run: `pytest tests/test_box_set_web.py -k "collection or add_title" -v`

Expected: FAIL for missing routes/UI.

- [ ] **Step 3: Register a dedicated `box_sets` blueprint**

In `movie_catalogue/__init__.py`:

```python
from .box_sets import bp as box_sets_bp
app.register_blueprint(box_sets_bp)
```

In `box_sets.py` use `Blueprint("box_sets", __name__)`, `login_required`, and `require_library_role("editor")` for add/edit actions.

- [ ] **Step 4: Add explicit Collection / Box Set mode to Add Title**

In `movie_lookup.html`, add a third option:

```html
<option value="collection">Movie Collection / Box Set</option>
```

When `media_type=collection`, do not call `_tmdb_search`; redirect or link to `box_sets.new_box_set` with the query. Movie remains the default.

- [ ] **Step 5: Build confirmation UI with physical metadata and default-selected members**

The form includes `title`, `barcode`, `format`, `version`, `country`, `language`, `region`, `disc_count`, `notes`, `shelf_id`, and repeated member checkboxes. TMDb collection title/poster and each part title/year/poster are display-only and revalidated server-side on POST.

- [ ] **Step 6: Run web-flow tests**

Run: `pytest tests/test_box_set_web.py -k "collection or add_title" -v`

Expected: PASS.

- [ ] **Step 7: Commit Add flow**

```bash
git add movie_catalogue/box_sets.py movie_catalogue/__init__.py movie_catalogue/templates/box_set_lookup.html movie_catalogue/templates/box_set_confirm.html movie_catalogue/templates/movie_lookup.html movie_catalogue/static/styles.css tests/test_box_set_web.py
git commit -m "feat: add TMDb box set creation flow"
```

---

### Task 6: Add box-set detail, editing, member correction, and safe deletion

**Files:**
- Modify: `movie_catalogue/box_sets.py`
- Modify: `movie_catalogue/box_set_service.py`
- Create: `movie_catalogue/templates/box_set_detail.html`
- Create: `movie_catalogue/templates/box_set_edit.html`
- Modify: `movie_catalogue/static/styles.css`
- Test: `tests/test_box_set_web.py`

**Interfaces:**
- Routes:
  - `GET /libraries/<library_id>/box-sets/<box_set_id>`
  - `GET|POST /libraries/<library_id>/box-sets/<box_set_id>/edit`
  - `POST /libraries/<library_id>/box-sets/<box_set_id>/members/add`
  - `POST /libraries/<library_id>/box-sets/<box_set_id>/members/<member_id>/remove`
  - `POST /libraries/<library_id>/box-sets/<box_set_id>/members/reorder`
  - `POST /libraries/<library_id>/box-sets/<box_set_id>/delete`
- Member add searches TMDb Movie only.
- Member removal is blocked while that member has an active loan.
- Box-set deletion is blocked when any active loan exists and requires title confirmation. Preserve loan history by blocking deletion when historical loan rows exist in this first release rather than silently cascading them away.

- [ ] **Step 1: Write failing detail/member/deletion tests**

Cover:
- detail renders members in `position,id` order;
- manual member add uses movie TMDb search only;
- removing actively loaned member returns a warning and leaves row intact;
- deleting a set with any loan history is blocked;
- deleting a never-loaned set after exact title confirmation removes parent and members.

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest tests/test_box_set_web.py -k "detail or member or delete" -v`

- [ ] **Step 3: Implement detail/edit/member routes using service helpers**

Keep physical metadata on `box_sets`; `box_set_members` only accept canonical identity/display fields and `position`.

- [ ] **Step 4: Implement deletion guards before issuing DELETE**

Query both loan tables for active/history rows. If any history exists, flash an explicit message such as `This box set has loan history and cannot be deleted in this release.` and leave all rows unchanged.

- [ ] **Step 5: Run detail/member/deletion tests**

Run: `pytest tests/test_box_set_web.py -k "detail or member or delete" -v`

Expected: PASS.

- [ ] **Step 6: Commit detail management**

```bash
git add movie_catalogue/box_sets.py movie_catalogue/box_set_service.py movie_catalogue/templates/box_set_detail.html movie_catalogue/templates/box_set_edit.html movie_catalogue/static/styles.css tests/test_box_set_web.py
git commit -m "feat: manage physical box set contents"
```

---

### Task 7: Merge box sets and optional contained films into library browsing/search

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/catalogue.html`
- Modify: `movie_catalogue/libraries.py`
- Modify: `movie_catalogue/templates/library_settings.html`
- Modify: `movie_catalogue/static/styles.css`
- Test: `tests/test_box_set_web.py`

**Interfaces:**
- Library setting POST endpoint: `POST /libraries/<library_id>/settings/box-set-members` or equivalent focused route in `libraries.py`.
- Catalogue card dictionaries gain `item_type`:
  - `movie`
  - `box_set`
  - `box_set_member`
- Box-set member virtual card carries `box_set_id`, `box_set_title`, and effective loan state; it never exposes a fake standalone movie ID.

- [ ] **Step 1: Write failing grid/search/count/settings tests**

Cover:

```python
def test_default_grid_shows_box_set_once_and_hides_members(...): ...
def test_setting_shows_member_virtual_cards_without_hiding_parent(...): ...
def test_search_finds_hidden_member_even_when_setting_off(...): ...
def test_search_hidden_member_links_to_parent_box_set(...): ...
def test_physical_count_counts_box_set_once_not_each_member(...): ...
def test_library_setting_defaults_off_and_persists(...): ...
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest tests/test_box_set_web.py -k "grid or search or setting or count" -v`

- [ ] **Step 3: Add setting persistence**

Only owners/editors may change it. Store `1` when checkbox is present, else `0`:

```python
db.execute(
    "UPDATE libraries SET show_box_set_members=? WHERE id=?",
    (1 if request.form.get("show_box_set_members") else 0, library_id),
)
```

- [ ] **Step 4: Build a unified display list without changing physical movie rows**

Keep `_group_movie_rows()` for movies. Query physical box sets separately with current whole/member loan summaries. Build display cards with explicit `item_type`; do not insert synthetic records into `movies`.

Search behavior when `q` is non-empty must include a box set if:
- box-set title/barcode/notes matches, or
- any `box_set_members.title` matches.

If the query matches a hidden member, include a virtual member result pointing to the parent even when `show_box_set_members=0`; this is the exception that makes hidden members searchable.

- [ ] **Step 5: Update physical statistics**

Primary count = grouped standalone physical movie identities/copies as currently defined for UI + physical box sets, never member rows. Also calculate `contained_titles` for an optional secondary `N contained films` display.

- [ ] **Step 6: Render item-type-specific cards**

`catalogue.html` must route:
- movie → `catalog.movie_detail`
- box_set → `box_sets.detail`
- box_set_member → `box_sets.detail` with `#member-<id>` anchor

Member cards get `In box set` and parent title; box-set cards get `Movie Box Set` and film count.

- [ ] **Step 7: Run catalogue/settings tests and existing catalogue regressions**

Run: `pytest tests/test_box_set_web.py tests/test_catalog_features.py -v`

Expected: PASS.

- [ ] **Step 8: Commit browsing/search behavior**

```bash
git add movie_catalogue/catalog.py movie_catalogue/libraries.py movie_catalogue/templates/catalogue.html movie_catalogue/templates/library_settings.html movie_catalogue/static/styles.css tests/test_box_set_web.py
git commit -m "feat: browse and search box set contents"
```

---

### Task 8: Implement whole-set and individual-member loans

**Files:**
- Modify: `movie_catalogue/box_set_service.py`
- Modify: `movie_catalogue/box_sets.py`
- Modify: `movie_catalogue/templates/box_set_detail.html`
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/loans.html`
- Create: `tests/test_box_set_loans.py`

**Interfaces:**
- Service functions:
  - `loan_box_set(db, library_id, box_set_id, borrower_name, phone, loaned_date, notes)`
  - `return_box_set(db, library_id, box_set_id, returned_date)`
  - `loan_box_set_member(db, library_id, member_id, borrower_name, phone, loaned_date, notes)`
  - `return_box_set_member(db, library_id, member_id, returned_date)`
- Violations raise a small domain exception `BoxSetLoanConflict(message)` caught by web/API layers.

- [ ] **Step 1: Write loan-rule tests first**

Required tests:

```python
def test_whole_set_loan_marks_every_member_effectively_loaned(...): ...
def test_whole_set_loan_blocks_individual_member_loan(...): ...
def test_individual_member_loan_blocks_whole_set_loan(...): ...
def test_return_whole_set_restores_member_availability(...): ...
def test_return_member_restores_whole_set_loan_eligibility(...): ...
def test_parent_shows_incomplete_when_one_member_is_out(...): ...
def test_existing_standalone_movie_loan_still_works(...): ...
```

- [ ] **Step 2: Run the loan tests and verify RED**

Run: `pytest tests/test_box_set_loans.py -v`

- [ ] **Step 3: Implement conflict checks inside service functions**

Before whole-set insert:

```sql
SELECT 1
FROM box_set_member_loans bml
JOIN box_set_members bsm ON bsm.id=bml.box_set_member_id
WHERE bsm.box_set_id=? AND bml.returned_date IS NULL
LIMIT 1
```

Before member insert, join its parent and reject if active `box_set_loans` exists. Do not create child loan rows for a whole-set loan.

- [ ] **Step 4: Add web loan/return routes and effective states**

Routes:
- `POST .../box-sets/<id>/loan`
- `POST .../box-sets/<id>/return`
- `POST .../box-sets/<id>/members/<member_id>/loan`
- `POST .../box-sets/<id>/members/<member_id>/return`

The detail page disables conflicting actions and labels states `Loaned with box set`, `Loaned individually`, and `Incomplete / member loaned`.

- [ ] **Step 5: Include all loan types on `/loans`**

Build a normalized list with `loan_kind` in `{movie, box_set, box_set_member}`, title/parent title, borrower/date/phone/notes, detail URL, and return URL. Do not alter the existing loan history tables.

- [ ] **Step 6: Run loan and standalone regression tests**

Run: `pytest tests/test_box_set_loans.py tests/test_catalog_features.py -k "loan or return" -v`

Expected: PASS.

- [ ] **Step 7: Commit loan behavior**

```bash
git add movie_catalogue/box_set_service.py movie_catalogue/box_sets.py movie_catalogue/catalog.py movie_catalogue/templates/box_set_detail.html movie_catalogue/templates/loans.html tests/test_box_set_loans.py
git commit -m "feat: support box set and member loans"
```

---

### Task 9: Add separate box-set CSV import/export

**Files:**
- Modify: `movie_catalogue/box_sets.py`
- Modify: `movie_catalogue/templates/catalogue.html`
- Create: `tests/test_box_set_csv.py`

**Interfaces:**
- `GET /libraries/<library_id>/box-sets/export.csv`
- `POST /libraries/<library_id>/box-sets/import.csv`
- CSV row type is explicit and independent from existing movie CSV.

Use one row per contained member while repeating parent physical fields, with these exact headers:

```text
box_set_key,barcode,title,tmdb_collection_id,poster_path,format,version,country,language,region,disc_count,notes,shelf,member_tmdb_id,member_title,member_year,member_poster_path,member_position
```

`box_set_key` is an export-local stable key such as the box-set database ID represented as text; import groups rows by key and creates one parent per key.

- [ ] **Step 1: Write failing CSV round-trip tests**

Cover:
- export emits one parent repeated across member rows;
- import of two member rows creates one `box_sets` row and two members;
- malformed member row aborts that parent group rather than half-creating it;
- existing `/export.csv` movie header/output remains unchanged.

- [ ] **Step 2: Run CSV tests and verify RED**

Run: `pytest tests/test_box_set_csv.py tests/test_catalog_features.py::test_csv_export_is_scoped_to_library -v`

- [ ] **Step 3: Implement dedicated CSV routes using `create_box_set()` transaction helper**

Validate shelf by library name/ID using existing conventions; ignore unknown shelf by setting it unassigned rather than attaching cross-library IDs.

- [ ] **Step 4: Add separate toolbar controls**

Keep current `Export CSV` / movie import untouched. Add `Export Box Sets CSV` and `Import Box Sets CSV` labels so users cannot confuse formats.

- [ ] **Step 5: Run CSV regressions**

Run: `pytest tests/test_box_set_csv.py tests/test_catalog_features.py::test_csv_export_is_scoped_to_library -v`

Expected: PASS.

- [ ] **Step 6: Commit CSV support**

```bash
git add movie_catalogue/box_sets.py movie_catalogue/templates/catalogue.html tests/test_box_set_csv.py
git commit -m "feat: import and export box sets"
```

---

### Task 10: Expose first-class box-set API and Collection barcode mode

**Files:**
- Modify: `movie_catalogue/mobile_api.py`
- Modify: `movie_catalogue/integrations.py`
- Modify: `API.md`
- Create: `tests/test_box_set_api.py`

**Interfaces:**
- `GET /api/v1/box-sets?library_id=&q=`
- `GET /api/v1/box-sets/<id>`
- `POST /api/v1/box-sets`
- `POST /api/v1/box-sets/<id>/loan`
- `POST /api/v1/box-sets/<id>/return`
- `POST /api/v1/box-set-members/<id>/loan`
- `POST /api/v1/box-set-members/<id>/return`
- `GET /api/v1/tmdb/collections/search?q=`
- `GET /api/v1/tmdb/collections/<id>`
- `GET /api/v1/barcodes/<upc>?media_type=collection`

Box-set JSON shape:

```json
{
  "id": 12,
  "library_id": 3,
  "title": "Harry Potter 8-Film Collection",
  "tmdb_collection_id": 1241,
  "poster_path": "https://image.tmdb.org/...",
  "format": "Blu-ray",
  "barcode": "...",
  "disc_count": 11,
  "loan_state": "available",
  "members": [
    {"id": 99, "tmdb_id": 671, "title": "...", "year": 2001, "poster_path": "...", "loan_state": "available"}
  ]
}
```

- [ ] **Step 1: Write failing API authorization/shape tests**

Cover viewer list/detail, editor create/loan, viewer create rejection, library scoping, hidden-member search, and conflict responses (`409` for mutually exclusive loan conflicts).

- [ ] **Step 2: Write a barcode Collection-mode test**

Patch product lookup to return `Harry Potter 8-Film Collection Blu-ray`, patch `tmdb_collection_search`, call `?media_type=collection`, and assert exactly one collection search is made and no movie/TV search is made.

- [ ] **Step 3: Run API tests and verify RED**

Run: `pytest tests/test_box_set_api.py -v`

- [ ] **Step 4: Implement API serializers/routes using the shared service**

Do not duplicate loan-state rules in `mobile_api.py`; catch `BoxSetLoanConflict` and return `409` JSON.

- [ ] **Step 5: Extend barcode lookup mode explicitly**

Accept only `movie`, `tv`, or `collection`. In Collection mode:
- use `movie_box_set_title_candidates()`;
- query `tmdb_collection_search()` only;
- return collection candidates and physical metadata parsed from the UPC title;
- never fall through to `_barcode_tmdb_matches()` for movie/TV.

- [ ] **Step 6: Document endpoints in `API.md` and run API regressions**

Run: `pytest tests/test_box_set_api.py tests/test_mobile_api.py -v`

Expected: PASS.

- [ ] **Step 7: Commit API support**

```bash
git add movie_catalogue/mobile_api.py movie_catalogue/integrations.py API.md tests/test_box_set_api.py
git commit -m "feat: expose box sets in mobile API"
```

---

### Task 11: Integrate library destructive operations and permissions

**Files:**
- Modify: `movie_catalogue/libraries.py`
- Modify: `movie_catalogue/templates/library_settings.html`
- Test: `tests/test_box_set_web.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- `Clear all movies` is renamed in copy to `Clear all titles / box sets` or explicitly states that it removes both standalone movies and box sets.
- Existing backup-first behavior remains in place.
- Viewer/editor/owner permission levels remain unchanged.

- [ ] **Step 1: Write failing destructive-operation and permission tests**

Cover:
- viewer cannot create/edit/delete/loan box sets;
- editor can manage box sets but cannot change owner-only library operations if current policy forbids them;
- clearing a library removes both movies and box sets after the existing confirmation phrase and backup;
- deleting a library cascades box-set data through library FK.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/test_box_set_web.py -k "clear or permission" tests/test_permissions.py -v`

- [ ] **Step 3: Extend clear-library behavior to box-set tables**

Use parent deletes (`DELETE FROM box_sets WHERE library_id=?`) and let members cascade. Preserve current backup call before destructive changes.

- [ ] **Step 4: Update settings copy and run permission/destructive tests**

Run: `pytest tests/test_box_set_web.py -k "clear or permission" tests/test_permissions.py -v`

Expected: PASS.

- [ ] **Step 5: Commit integration safeguards**

```bash
git add movie_catalogue/libraries.py movie_catalogue/templates/library_settings.html tests/test_box_set_web.py tests/test_permissions.py
git commit -m "fix: integrate box sets with library safeguards"
```

---

### Task 12: Version, documentation, template validation, and release verification

**Files:**
- Modify: `movie_catalogue/config.py`
- Modify: `README.md`
- Modify/Create: source-contract tests as needed under `tests/`

**Interfaces:**
- Server release version becomes `0.3.27`.
- Android remains at its prior app version for this web/server-first release unless actual Android UI work is separately approved and implemented.

- [ ] **Step 1: Add source-contract assertions for the architectural guarantees**

Create a small standalone/source contract that asserts:
- `box_sets` blueprint is registered;
- Collection search points to `/search/collection`;
- API accepts explicit `collection` mode;
- `libraries.show_box_set_members` exists;
- no box-set code inserts contained films into `movies`.

- [ ] **Step 2: Bump server version and document the feature**

Set:

```python
APP_VERSION = "0.3.27"
```

README release notes must state:
- physical movie box sets are one inventory item;
- TMDb Collection can populate films;
- member titles are hidden from main grid by default but searchable;
- library setting can show them;
- whole-set and individual-film loans are supported;
- disc mapping is intentionally not tracked;
- Android UI for box sets is deferred even though server API support is present.

- [ ] **Step 3: Run the complete available Python regression suite**

Preferred when dependencies are present:

```bash
pytest -q
```

Always run standalone checks:

```bash
python tests/standalone_barcode_parser_checks.py
python tests/standalone_v0317_identify_parser_checks.py
python tests/standalone_v0318_smart_matching_checks.py
python tests/standalone_v0319_metadata_repair_checks.py
python tests/standalone_v0320_scanner_shared_pipeline_checks.py
python tests/standalone_v0324_tv_behavior_checks.py
python tests/standalone_v0325_tv_set_parser_checks.py
python tests/standalone_v0326_identify_tv_override_checks.py
python tests/standalone_v0327_box_set_parser_checks.py
python -m compileall -q movie_catalogue tests
```

If Flask remains unavailable in the execution environment, explicitly report `pytest` as unavailable and do not imply it passed.

- [ ] **Step 4: Validate all Jinja templates compile**

Use the Flask/Jinja environment when available to load every template under `movie_catalogue/templates`; fail on syntax errors.

- [ ] **Step 5: Run Android source and signing regressions without rebuilding the app**

```bash
cd android
python source-checks.py
python url-regression-check.py
cd ..
```

Also scan the release tree and confirm no `.jks`, `.keystore`, or non-example `keystore.properties` is present.

- [ ] **Step 6: Perform a focused manual smoke test with an isolated SQLite database**

Verify this exact scenario:
1. Add `Harry Potter 8-Film Collection Blu-ray` in Collection mode.
2. Select TMDb Harry Potter Collection and save eight members.
3. Main grid shows one box-set card by default.
4. Search `Prisoner of Azkaban` finds the contained title.
5. Enable `Show films contained in box sets`; member cards appear with `In box set` labels.
6. Loan `Prisoner of Azkaban` individually; parent becomes incomplete and whole-set loan is blocked.
7. Return it; loan whole set; every member reports `Loaned with box set`.
8. Return whole set; all members become available.

- [ ] **Step 7: Build and validate the release ZIP**

Name: `Homebuster-v0.3.27-web-plus-android.zip`.

Run ZIP integrity verification and SHA-256. Exclude `__pycache__`, `.pytest_cache`, generated database files, signing secrets, and local environment files.

- [ ] **Step 8: Commit release metadata**

```bash
git add movie_catalogue/config.py README.md tests docs/superpowers/specs/2026-09-14-physical-box-sets-design.md docs/superpowers/plans/2026-09-14-physical-box-sets.md
git commit -m "docs: release Homebuster 0.3.27 box sets"
```

---

## Self-Review

### Spec coverage

- Dedicated physical parent + member schema: Tasks 1 and 4.
- TMDb Collection-only lookup and ordered parts: Task 2.
- Conservative automatic box-set hinting without multi-endpoint fan-out: Tasks 3, 5, and 10.
- Confirmation checklist / subset selection: Task 5.
- Default single parent card, optional member grid, hidden-member search, physical counts: Task 7.
- Box-set detail, editing, member correction/reordering: Task 6.
- Whole-set/member loan exclusivity and effective states: Task 8.
- No disc mapping: global constraint and no schema field introduced.
- Existing Homebuster Collections unchanged: global constraint; no modifications to `collections`/`movie_collections` schema.
- Separate box-set CSV: Task 9.
- API-first Android preparation with UI deferred: Task 10 and Task 12.
- Additive migration and existing-db compatibility: Task 1.
- Failure handling/transactional creation: Tasks 4 and 5.
- Destructive operation/permission integration: Tasks 6 and 11.

### Placeholder scan

No `TBD`, `TODO`, “implement later”, or unspecified “write tests” steps remain. Android UI is deliberately out of scope per the approved spec, not an implementation placeholder.

### Type/interface consistency

- Shared creation path is `create_box_set(db, library_id, physical, members) -> int` throughout.
- Shared conflict type is `BoxSetLoanConflict` in both web and API layers.
- Display `item_type` values are consistently `movie`, `box_set`, `box_set_member`.
- Explicit external lookup mode is consistently `collection`; stored standalone media types remain only `movie`/`tv`.
- Parent collection identity is consistently `tmdb_collection_id`; member canonical movie identity is `tmdb_id`.
