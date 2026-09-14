# Library Default Content Type Design

**Version target:** Homebuster v0.3.39  
**Date:** 2026-09-14

## Purpose

Give every Homebuster library a preferred/default TMDb content type without restricting what that library may contain. A library may default to Movies, TV Shows, or Movie Collections / Box Sets, while still freely containing all supported content types.

The library preference expresses **intent for the next operation**. Existing item `media_type` expresses **what an already-identified item actually is**.

## User-facing names and stored values

| UI label | Stored/API value |
| --- | --- |
| Movies | `movie` |
| TV Shows | `tv` |
| Movie Collections / Box Sets | `collection` |

Only these three values are valid.

## Migration and persistence

Add `libraries.default_media_type TEXT NOT NULL DEFAULT 'movie'`.

Existing libraries automatically receive `movie`. This migration must not update any movie, box-set, TMDb identity, review state, or other inventory metadata.

New-library creation requires a Default content type selector and persists the selected value. The default selection is Movies.

Library Settings exposes the same selector to the library owner. Changing it only changes `libraries.default_media_type`; it must not trigger matching, conversion, refresh, or edits to existing inventory.

## Default-versus-override rule

Whenever a workflow needs an initial search type and the user did not explicitly choose one, use `library.default_media_type`.

An explicit Movie/TV/Collection selection is a **one-operation override**. It is carried only as far as necessary to complete that operation or its immediate review continuation. It is never saved back to the library and never stored in browser preferences.

The next newly-started operation returns to the library default.

For operations on an already TMDb-matched item, the stored item `media_type` remains authoritative when refreshing its existing metadata. The library default must never cause a matched TV record to be refreshed through the Movie endpoint, for example.

## Web behavior

### Add / TMDb lookup

The existing add/lookup workflow starts its type selector at the library default. The user may switch it for that lookup only.

### Identify with TMDb

When opening Identify without an explicit `media_type` query parameter, start with the library default for an unresolved top-level item. An explicit `media_type` parameter overrides it for that Identify operation.

Contained box-set member constraints remain unchanged: a contained film cannot be converted into another collection.

After a successful identification, no type choice is persisted to the library preference.

### Match / Repair

The Match / Repair page renders its TMDb Search Type selector with the library default selected.

The selected type is sent explicitly to each bulk batch and remains the type for that run. It does not alter the library setting.

When `Refresh metadata for already matched movies` is enabled, each matched item's stored `media_type` continues to control its refresh endpoint. The bulk selector/library default only governs unresolved items.

### Mass Review

When Mass Review is entered as the continuation of a bulk run, the run's explicit search type continues through that review queue.

When Mass Review is opened as a fresh operation without an explicit type, it starts from the library default. Changing the review type is an operation-level override and does not change the library.

### Imports

CSV import semantics do not change. Imported/stored media types are not rewritten to the library default.

## Android and API behavior

The server remains authoritative for the library preference.

`GET /api/v1/libraries` adds `default_media_type` to every library object. This is additive and backward-compatible for older clients.

The Android app models that field with a Kotlin default of `"movie"` so it remains compatible with older servers.

The Android app must know which library is active for scanning. The barcode-result workflow initializes its `mediaType` state from that active library's `defaultMediaType`. The user may switch Movie/TV/Collection for that barcode lookup; the override lasts only for that scanned operation. A new scan initializes from the library default again.

Barcode and TMDb requests continue sending an explicit `media_type`, preserving the existing API's no-fan-out behavior. Homebuster must not automatically query Movie + TV + Collection endpoints.

The Android scanner default must not be a separate saved preference.

## Permissions

Creating a library sets its default type.

Changing an existing library's default type is a library-settings operation and follows the existing settings ownership model. It is not an admin/global setting.

## Non-goals

- No separate Movie-library, TV-library, or Collection-library database types.
- No restriction on which item types may coexist in a library.
- No automatic conversion or rematching when the library default changes.
- No automatic Movie/TV/Collection endpoint fan-out.
- No persistent per-user or per-device override.
- No renaming of Add Movie to Add Item in this release.
- No episode tracking.

## Compatibility and validation

Unknown/invalid submitted library default values are rejected or normalized to the safe `movie` default at trust boundaries; persisted values are always one of `movie`, `tv`, `collection`.

Existing databases migrate in place with Movie as the default. Existing Android clients may ignore the additive API field and continue behaving as before.

## Acceptance criteria

1. Existing libraries become Movie-default without inventory changes.
2. New libraries can choose Movies, TV Shows, or Movie Collections / Box Sets.
3. Owners can change the default later without touching existing inventory.
4. Fresh Add, Identify, Match/Repair, and Review flows use the library default.
5. One-time selector overrides work and never alter the library setting.
6. Matched-item metadata refresh continues to use the item's stored type.
7. `GET /api/v1/libraries` returns `default_media_type`.
8. Android barcode lookup starts from the active library default and resets to it on the next scan.
9. No workflow automatically fans out across all TMDb content types.
