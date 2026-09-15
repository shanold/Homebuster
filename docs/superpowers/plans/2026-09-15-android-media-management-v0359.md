# Android Media Management v0.3.59 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Android media management match the web app's physical-copy workflow: controlled format/shelf editing, richer optional metadata, browsable shelves/collections, and a complete loan form that acts on an exact physical copy.

**Architecture:** Keep title grouping for browsing but require an exact `movies.id` physical copy before edit/loan/return mutations. Extend the bearer-token API only where the Android client needs missing data/actions. Use the existing web format vocabulary and SQLite loan model.

**Tech Stack:** Flask/SQLite, Kotlin/Jetpack Compose, Retrofit.

**Spec:** Approved conversation design, 2026-09-15.

## Global Constraints
- v0.3.58 is source of truth.
- Format choices exactly match web: Blu-ray, Blu-ray + DVD, 4K, 4K UHD, DVD, HD DVD, VHS, Other.
- Viewer accounts remain read-only.
- A grouped title never sends a mutation until a concrete physical copy is selected.
- Loan form supports borrower, optional phone, date, and notes.
- Collections and shelves must open into media lists.
- Extra metadata stays behind More Info.
- No site-admin or bulk-maintenance Android work.

---

### Task 1: Regression tests and loan root-cause guard
Write failing source checks for exact-copy mutations, format choices, loan date handling, browse endpoints, More Info, and new screens.

### Task 2: Mobile API
Add shelf-detail movies endpoint; accept/validate loan date; retain permission checks; expose sufficient physical-copy metadata.

### Task 3: Retrofit models
Add movie status/notes/loan state, loan date request, shelf media endpoint, and any response models required by the UI.

### Task 4: Android detail/edit/loan
Replace free-text format with controlled selector, add shelf selector, keep extra metadata behind More Info, make physical-copy selection explicit, and use a dedicated full loan screen.

### Task 5: Android shelf/collection browsing
Make shelf and collection rows tappable and show their contained media.

### Task 6: Verification and release
Run the dedicated v0.3.59 regression, Python compile, Jinja parse, Android source structural checks, then package v0.3.59. Do not claim a Gradle build without a usable wrapper/environment.
