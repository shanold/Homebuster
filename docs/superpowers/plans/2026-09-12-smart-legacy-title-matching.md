# Smart Legacy Title Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Identify and Match / Repair use multiple conservative title interpretations so old imported/scanned titles with format, edition, packaging, parenthetical notes, or minor typos can still find TMDb candidates without blindly rewriting library data.

**Architecture:** Add reusable pure matching helpers to `movie_catalogue/barcode_parser.py` that generate safe search candidates and evaluate high-confidence fuzzy matches. Update `movie_catalogue/catalog.py` to query TMDb with multiple candidates, merge/deduplicate results for manual Identify, and use the same candidates plus conservative acceptance for bulk Match / Repair. Stored titles remain unchanged until a TMDb result is explicitly chosen or automatically accepted at high confidence.

**Tech Stack:** Python 3, Flask, SQLite, TMDb HTTP API, existing barcode parser/ranking helpers.

**Spec:** Approved in chat on 2026-09-12: candidate-based cleanup, punctuation/parenthetical/edition/format handling, typo tolerance, high-confidence-only bulk matching, no destructive rewrite before match.

## Global Constraints

- Preserve all existing web and Android functionality.
- Keep Android at v0.3.16/versionCode 14 because this is server-side only.
- Bump server `APP_VERSION` to 0.3.18.
- Do not auto-convert box-set/collection names to a single film unless confidence is genuinely decisive.
- Do not alter barcode, format, version, country, language, region, disc count, notes, shelf, collections, loans, or status during matching.
- Do not overwrite a stored title until a TMDb match has been accepted.

---

### Task 1: Candidate generator

**Files:**
- Modify: `movie_catalogue/barcode_parser.py`
- Create: `tests/standalone_v0318_smart_matching_checks.py`

**Interfaces:**
- Produces: `generate_movie_title_candidates(raw_title: str) -> list[str]`

- [ ] **Step 1: Write failing standalone tests** for `Beauty and the beast, DVD and Blu-ray`, `Bambi Diamond Edition`, `An American Tale(Fievel)`, and `Ace Ventura collection`.
- [ ] **Step 2: Run the standalone test and verify it fails because the helper does not exist.**
- [ ] **Step 3: Implement candidate generation** using existing parser output plus conservative generic transformations: punctuation cleanup, removable parenthetical notes, generic edition suffixes, media-format/connective cleanup, and collection suffix as an alternate candidate only.
- [ ] **Step 4: Re-run the standalone test and existing barcode parser checks.**

### Task 2: Conservative typo-aware confidence

**Files:**
- Modify: `movie_catalogue/barcode_parser.py`
- Modify: `tests/standalone_v0318_smart_matching_checks.py`

**Interfaces:**
- Produces: `high_confidence_tmdb_match(query_titles, query_year, results) -> dict | None`

- [ ] **Step 1: Add failing cases** proving `An American Tale` can confidently match `An American Tail` when clearly dominant, `Ace Ventura` does not auto-match `Ace Ventura: Pet Detective`, and ambiguous same-title `Bambi` results remain unmatched without a year.
- [ ] **Step 2: Run and verify RED.**
- [ ] **Step 3: Implement minimal confidence logic** that takes the best score across candidate titles, permits only very-close typo matches with a clear margin, and retains exact-title ambiguity protection.
- [ ] **Step 4: Run checks until GREEN.**

### Task 3: Multi-query Identify and Match / Repair

**Files:**
- Modify: `movie_catalogue/catalog.py`
- Modify: `tests/test_v0318_source_contract.py`

**Interfaces:**
- Consumes: `generate_movie_title_candidates`, `high_confidence_tmdb_match`
- Produces: `_match_queries_for_movie(movie)` and merged TMDb search behavior.

- [ ] **Step 1: Write a failing source-contract test** requiring both Identify and Match / Repair to use multi-candidate search and deduplicate TMDb results.
- [ ] **Step 2: Run and verify RED.**
- [ ] **Step 3: Implement `_match_queries_for_movie` and `_tmdb_search_candidates`**. Manual Identify returns merged results from all candidates. Bulk matching evaluates the merged result set against all candidate titles.
- [ ] **Step 4: Run source contract plus standalone matching checks.**

### Task 4: Version/docs/package verification

**Files:**
- Modify: `movie_catalogue/config.py`
- Modify: `README.md`
- Modify: version-sensitive source tests as needed

**Interfaces:**
- Server reports v0.3.18; Android remains v0.3.16/versionCode 14.

- [ ] **Step 1: Update server version and README notes.**
- [ ] **Step 2: Run Python compile checks, standalone parser tests, source-contract tests, and Android source/regression checks.**
- [ ] **Step 3: Confirm no signing key or real `keystore.properties` is present.**
- [ ] **Step 4: Package `Homebuster-v0.3.18-web-plus-android.zip`, run ZIP integrity test, and compute SHA-256.**
