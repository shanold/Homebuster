# Smart Legacy Metadata Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make legacy Identify / Match Repair use TMDb-confirmed canonical titles to recover physical-copy metadata from noisy stored titles, while processing bulk repair in visible committed batches with bounded TMDb usage.

**Architecture:** Keep the existing barcode parser as the shared source of structured metadata, but add a second canonical-title-anchored extraction pass that can find metadata anywhere in the leftover product description. Bulk repair moves from one long POST to a progress page plus stateless batch endpoint; every batch commits and returns counts to the browser. Bulk unmatched matching searches at most three title candidates per movie and stops as soon as a high-confidence match is established.

**Tech Stack:** Python 3, Flask, SQLite, Jinja, browser JavaScript, TMDb HTTP API.

**Spec:** Approved in chat on 2026-09-13.

## Global Constraints

- Preserve high-confidence-only automatic TMDb matching.
- Never overwrite manually populated physical-copy metadata; fill only blank/Unknown values.
- Move detected edition, format, language, region and disc count into their dedicated movie fields.
- Recognize metadata independent of suffix ordering after a canonical TMDb title is known.
- Bound unmatched TMDb search to at most three candidate searches per movie and stop early on a decisive match.
- Commit each bulk batch so a timeout/reload does not discard all progress.
- Android behavior remains unchanged; no Android rebuild required.

---

### Task 1: Canonical-title anchored metadata extraction

**Files:**
- Modify: `movie_catalogue/barcode_parser.py`
- Create: `tests/standalone_v0319_metadata_repair_checks.py`

**Interfaces:**
- Produces: `infer_copy_metadata_from_legacy_title(raw_title: str, canonical_title: str) -> dict`

- [ ] Write a failing standalone test covering mixed-order Blu-ray/DVD, numeric and word disc counts, generic `... Edition`, region/language, and preservation of movie-title words.
- [ ] Run the test and confirm the new helper is missing/failing.
- [ ] Implement independent metadata scanning plus canonical-title anchored generic-edition extraction.
- [ ] Re-run the standalone test and existing parser checks.

### Task 2: Apply recovered metadata during manual identification

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/identify.html`
- Create: `tests/test_v0319_source_contract.py`

**Interfaces:**
- Consumes: `infer_copy_metadata_from_legacy_title`
- Produces: fill-only metadata SQL update for Identify and per-result metadata preview.

- [ ] Write source-contract assertions for fill-only updates and preview data.
- [ ] Confirm the assertions fail against v0.3.18.
- [ ] Add helper for fill-only metadata updates and wire it into Identify POST/GET.
- [ ] Re-run source contract.

### Task 3: Batched Match / Repair with bounded TMDb searches

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `movie_catalogue/templates/catalogue.html`
- Create: `movie_catalogue/templates/match_repair.html`
- Modify: `tests/test_v0319_source_contract.py`

**Interfaces:**
- Produces: `GET /libraries/<id>/match-repair` progress UI and `POST /libraries/<id>/match-repair/batch` JSON batch endpoint.

- [ ] Add failing source-contract assertions for batch route, per-batch commit, three-query cap, and progress UI.
- [ ] Implement a high-confidence sequential search helper capped at three candidates.
- [ ] Implement batch endpoint processing a fixed number of rows after a cursor and committing the batch.
- [ ] Implement progress page JavaScript that repeatedly calls the batch endpoint and displays processed/matched/refreshed/metadata/unmatched/failed counts.
- [ ] Replace the catalogue POST form with a link to the progress page.
- [ ] Re-run source-contract checks.

### Task 4: Versioning, docs and packaging verification

**Files:**
- Modify: `movie_catalogue/config.py`
- Modify: `README.md`
- Modify: `android/source-checks.py` only if its expected server version requires synchronization; do not bump Android app version.

**Interfaces:** None.

- [ ] Bump server version to `0.3.19` and document server-only nature of this release.
- [ ] Run Python compile checks, standalone parser suites, source contracts, Android source/regression checks, and confirm signing secrets are absent.
- [ ] Create `Homebuster-v0.3.19-web-plus-android.zip`, run ZIP integrity test, and compute SHA-256.
