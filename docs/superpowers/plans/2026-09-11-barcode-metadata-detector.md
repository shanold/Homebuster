# Barcode Metadata Detector Implementation Plan

**Goal:** Parse messy barcode-provider product titles into structured movie metadata, search/rank TMDb with clean inputs and fallbacks, and let Android confirm/add the selected physical copy.

**Architecture:** Add a Flask-independent `barcode_parser.py` responsible only for text parsing and candidate scoring. `integrations.py` remains responsible for external UPC/TMDb calls, `mobile_api.py` orchestrates staged searches and persistence, and Android displays the structured parse plus ranked candidates and submits detected physical-copy metadata when adding.

**Constraints:** Preserve raw provider title; no schema migration; reuse existing movie columns for language/region/disc_count/version; distributor is lookup-only; keep existing web behavior and barcode-owned shortcut.

## Tasks
1. Add parser/scoring tests, then implement `barcode_parser.py`.
2. Adapt UPC lookup and barcode API to structured parser + staged TMDb ranking.
3. Extend movie-add API to persist detected metadata.
4. Extend Android API models and barcode confirmation/add UI.
5. Bump server/Android to v0.3.12 and verify parser tests, Python syntax, Android source contracts, web regression, and ZIP integrity.
