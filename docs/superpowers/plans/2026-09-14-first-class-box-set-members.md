# First-Class Box-Set Member Movies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote physical movie box-set members into first-class Homebuster movie rows and add Collection identification to Identify and persistent Review.

**Architecture:** Keep `box_sets` as the physical parent inventory object. Add nullable `movies.parent_box_set_id`; populate one normal movie row per TMDb collection part, derive physical context from the parent, reuse standard movie loans for child loans, and derive whole-set unavailability from `box_set_loans`. Retain legacy `box_set_members`/`box_set_member_loans` only as migration sources for v0.3.27 databases.

**Tech Stack:** Flask, SQLite, Jinja2, requests/TMDb, Kotlin/Compose source contracts.

**Spec:** `docs/superpowers/specs/2026-09-14-first-class-box-set-members-design.md`

## Global Constraints

- Movie, TV, and Collection searches remain explicit; never query all endpoints automatically.
- Existing v0.3.27 databases migrate additively and idempotently.
- Parent owns physical barcode/shelf/format/region/edition/disc count; child rows are title identities.
- Contained children use normal `loans`; whole-set loans remain `box_set_loans`.
- No disc-to-film mapping.
- Do not bundle release signing secrets.
- Preserve Movie/TV behavior and unresolved-only default Match/Repair behavior.

---

### Task 1: Schema and v0.3.27 migration
**Files:** Modify `movie_catalogue/db.py`; create `tests/standalone_v0328_first_class_schema_checks.py`.
**Produces:** `movies.parent_box_set_id`, index, migration from legacy members and member loans into movie rows/normal loans.
- [ ] Write failing source/SQLite migration regression.
- [ ] Verify failure on v0.3.27 schema.
- [ ] Add nullable parent FK column/index and idempotent legacy migration.
- [ ] Verify repeated migration creates no duplicate children/loans.

### Task 2: First-class box-set service
**Files:** Modify `movie_catalogue/box_set_service.py`; create `tests/standalone_v0328_box_set_service_checks.py`.
**Produces:** child movie query/population/reconciliation, child effective state, whole-set vs normal-loan conflict rules.
- [ ] Write failing service behavior checks.
- [ ] Replace runtime member reads with `movies.parent_box_set_id`.
- [ ] Reconcile collection parts transactionally without duplicate children.
- [ ] Use normal `loans` for child loans and enforce parent/child mutual exclusion.

### Task 3: Box-set web detail and member management
**Files:** Modify `movie_catalogue/box_sets.py`, `templates/box_set_detail.html`, `templates/box_set_confirm.html`, `templates/box_set_edit.html` as needed.
**Produces:** clickable child movie cards and first-class child management.
- [ ] Update routes to use child movie IDs.
- [ ] Make member titles/posters link to normal movie detail.
- [ ] Route individual loan actions through standard movie loan flow or equivalent full-field form.
- [ ] Preserve whole-set loan controls.

### Task 4: Library grid, search, and movie detail inheritance
**Files:** Modify `movie_catalogue/catalog.py`, `templates/catalogue.html`, `templates/movie_detail.html`.
**Produces:** hidden-by-default contained children, optional grid exposure, always-searchable children, inherited parent context.
- [ ] Write contract checks for parent filtering/search/detail context.
- [ ] Exclude child rows from default grid unless library setting enabled.
- [ ] Include child rows in search regardless of setting.
- [ ] Show `In box set` and parent physical context on child detail.

### Task 5: Standard loan flow integration
**Files:** Modify `movie_catalogue/catalog.py`, `templates/movie_detail.html`, `templates/loans.html`, service helpers.
**Produces:** normal borrower/phone/date/notes flow for contained films and correct effective availability.
- [ ] Add regression for child loan blocking whole set and vice versa.
- [ ] Reuse `loans` for contained children.
- [ ] Render whole-set-derived status as `Loaned with box set`.

### Task 6: Identify with TMDb Collection
**Files:** Modify `movie_catalogue/catalog.py`, `templates/identify.html`, `box_set_service.py`; create regression test.
**Produces:** Movie/TV/Collection selector and conversion of existing row into physical box set + first-class children.
- [ ] Verify stored Movie row switched to Collection uses Collection candidate cleaning/search.
- [ ] Add Collection endpoint branch without multi-endpoint probing.
- [ ] Convert selected inventory row while preserving copy metadata.
- [ ] Clear review state and redirect to new box-set detail.

### Task 7: Persistent Review Collection support
**Files:** Modify `movie_catalogue/catalog.py`, `templates/match_repair_review.html`; create regression test.
**Produces:** Collection selector and conversion from review queue.
- [ ] Add selected-type Collection search behavior.
- [ ] Add Collection result card/post action.
- [ ] Convert/populate set and remove source row from queue.

### Task 8: CSV and API compatibility
**Files:** Modify `movie_catalogue/catalog.py`, `movie_catalogue/box_sets.py`, `movie_catalogue/mobile_api.py`, `API.md`.
**Produces:** parent linkage preservation in movie CSV/API and first-class box-set children in API.
- [ ] Add `parent_box_set_id`/parent context to movie serialization/export.
- [ ] Prevent movie CSV import from silently detaching children where parent reference is resolvable.
- [ ] Update box-set API member payloads to first-class movie IDs.
- [ ] Keep old member endpoints compatible where practical or return clear errors.

### Task 9: Versioning, templates, Android source compatibility, and release verification
**Files:** Modify version sources/README/Android source checks as required; create v0.3.28 contracts.
**Produces:** packaged v0.3.28 source ZIP.
- [ ] Bump server to 0.3.28; only bump Android if source contract changes require it.
- [ ] Run all standalone regressions plus new v0.3.28 tests.
- [ ] Run Python compileall and Jinja parse.
- [ ] Run Android source and URL regression checks.
- [ ] Scan for signing secrets.
- [ ] Run ZIP integrity and SHA-256.
