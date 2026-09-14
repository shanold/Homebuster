# Homebuster TV Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add inventory-focused TV/box-set support while keeping Movie as the default TMDb mode and bringing Android to feature parity.

**Architecture:** Add an additive `media_type` column, normalize TMDb Movie/TV responses to Homebuster's existing title model, route matching by explicit/stored media type, and carry the value through web and mobile APIs. Keep all physical-copy structures shared.

**Tech Stack:** Flask, SQLite, Jinja, TMDb API, Kotlin, Jetpack Compose, Retrofit.

**Spec:** `docs/superpowers/specs/2026-09-13-tv-support-design.md`

## Global Constraints
- Existing rows default to `movie`.
- No episode or season database model.
- Movie search is the default; do not automatically search Movie and TV together.
- Existing physical metadata and library permissions remain unchanged.
- Android uses the Homebuster server API and does not call TMDb directly.

---

### Task 1: Persist media type
- [x] Write a failing source contract for `media_type` schema/migration.
- [x] Add `movies.media_type` with default `movie` and startup migration.
- [x] Carry the field through form/CSV/API writes.
- [x] Verify schema/default behavior with SQLite.

### Task 2: Make TMDb flows media-aware
- [x] Add explicit Movie/TV endpoint routing and normalized TV title/date fields.
- [x] Update Add, Identify, review, bulk repair, and metadata refresh to use selected/stored type.
- [x] Group copies by `(media_type, tmdb_id)`.
- [x] Add Movie/TV badges and selectors in web UI.

### Task 3: Android parity
- [x] Add `media_type` to Retrofit models and requests.
- [x] Group Android copies by media type + TMDb ID.
- [x] Add explicit Movie/TV barcode selector and TV-aware result/add flow.
- [x] Bump Android version with existing release-signing setup unchanged.

### Task 4: Regression and packaging
- [x] Run parser/scanner/source regressions, Python compilation, template parsing, secret scan, and ZIP integrity check.
- [x] Package v0.3.24 from the v0.3.23 pre-TV checkpoint.
