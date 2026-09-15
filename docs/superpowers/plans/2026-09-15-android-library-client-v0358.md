# Android Library Client v0.3.58 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Android from a scanner/viewer into an everyday Homebuster client and remove unsupported web camera scanning.
**Architecture:** Extend the existing bearer-token mobile API with permission-scoped mutation endpoints. Android gets Media, Collections, Loans and More/Shelves navigation while retaining the native scanner and shared barcode matching.
**Tech Stack:** Flask/SQLite, Kotlin/Jetpack Compose, Retrofit.
**Spec:** Approved conversation design, 2026-09-15.

## Global Constraints
- v0.3.57 is source of truth.
- Preserve viewer/editor permissions.
- Keep web smart title/UPC field; remove only browser camera scanner.
- Do not add site administration or bulk maintenance to Android.
- TDD for server/API and source-level Android regression checks.

---
### Task 1: Remove web BarcodeDetector UI
Write failing source regression; remove button/script camera path; preserve UPC smart field.

### Task 2: Mobile API mutations
Write failing API/source tests; add shelf assignment, movie edit/delete, loan/return, collection create/delete with library-role checks.

### Task 3: Android API models/client
Write failing source checks; expose detail, shelves, collections, loans and mutation calls.

### Task 4: Android everyday UI
Write failing source checks; implement Media/Collections/Loans/More navigation, detail/edit/loan/return, shelves and library switching; preserve scanner/add.

### Task 5: Release verification
Run standalone regressions, compile Python, parse Jinja, inspect Android source, package v0.3.58. Do not claim Gradle build without wrapper/build.
