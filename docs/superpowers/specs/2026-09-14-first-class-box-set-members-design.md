# Homebuster v0.3.28 — First-Class Box-Set Member Movies Design

## Status
Approved architecture revision for the physical movie box-set feature.

## Goal
Promote films contained in a physical movie box set from lightweight membership records into first-class Homebuster movie records, while preserving the physical box set as the parent inventory container. Also add Movie Collection / Box Set support to Identify with TMDb and persistent Mass Review.

## Core Model

### Physical box set
A physical box set remains the inventory container that owns copy-level data:

- UPC / barcode
- shelf location
- format
- region
- language
- edition
- total disc count
- notes
- overall loan state
- TMDb Collection identity and collection artwork

Example:

- Harry Potter Collection
- Blu-ray
- UPC 123456...
- Shelf A3
- 11 discs

### Contained movie
Every film inside the set is stored as a normal row in `movies`.

Contained movie rows retain normal title-level metadata:

- TMDb movie ID
- title
- year
- poster
- overview / synopsis where available
- runtime / genres where Homebuster already exposes them
- normal movie detail route
- normal movie loan metadata
- Homebuster user collections as supported by normal movies

A contained movie row gains a nullable parent relationship:

`parent_box_set_id`

A standalone movie has `parent_box_set_id = NULL`.

A movie contained in a box set points to the physical parent set.

Contained movies do not receive their own physical UPC, shelf, region, format, edition, or disc-count identity unless Homebuster later gains per-member copy overrides. They inherit the physical context of the parent box set for display.

## Library Browsing

### Default
The main library grid shows the physical box-set card once.

Contained member movies are hidden from the main grid by default.

Opening the box set displays its contained movies as clickable movie cards.

### Optional setting
Each library has:

`Show contained box-set movies in the main movie grid`

Default: Off.

When enabled, contained movies also appear in the normal movie grid with a visible `In box set` badge and a link/reference to their parent set.

This does not create duplicate rows. The same contained movie record is surfaced in another view.

### Search
Library search finds contained movies regardless of the grid-display setting.

A search result for a contained movie should indicate the parent box set so the user knows where the physical copy lives.

## Detail Pages

Contained movies use the normal movie-detail experience.

The page additionally shows:

- `Contained in: <Box Set Name>`
- inherited format
- inherited shelf
- inherited region / edition when available
- availability state
- link back to the box set

The physical box-set detail page shows the member films as clickable cards/list entries with poster, title, year, and current availability.

## Loans

### Individual contained-film loan
A contained movie uses the same loan workflow as a standalone movie.

It should support the same optional loan fields Homebuster already exposes for normal movie loans, rather than the v0.3.27 name-only member-loan form.

### Whole box-set loan
A whole-set loan marks every contained movie unavailable with a derived state such as:

`Loaned with box set`

The child rows do not need duplicate loan rows for a whole-set loan; their effective availability is derived from the parent loan.

### Mutual-exclusion rules

1. If any contained movie has an active individual loan, the entire box set cannot be loaned.
2. If the whole box set has an active loan, no contained movie can be loaned individually.
3. Returning an individual film makes only that child available again.
4. Returning the whole set restores availability for all children unless a future model adds another blocking state.

### Disc mapping
Homebuster intentionally does not model which movie is stored on which physical disc.

Contained movies are logically loanable independently even when a real retail release places multiple titles on one disc.

## TMDb Collection Creation

### Explicit Add flow
Add continues to offer:

- Movie
- TV Box Set
- Movie Collection / Box Set

Movie Collection / Box Set searches TMDb Collections only.

Selecting a TMDb Collection:

1. Creates or updates the physical box-set parent.
2. Fetches the TMDb Collection parts.
3. Creates one first-class `movies` row for every movie part.
4. Links each contained movie to the parent with `parent_box_set_id`.
5. Preserves the parent copy metadata from barcode/manual input.

### Barcode flow
Strong box-set wording can suggest Collection mode, but Homebuster must not automatically query Movie, TV, and Collection endpoints together.

The user-selected endpoint remains authoritative to control TMDb request volume.

## Identify with TMDb

Identify gets a third selector:

- Movie
- TV Box Set
- Movie Collection / Box Set

The currently selected type controls both:

- candidate-title cleanup
- TMDb endpoint

This must not repeat the earlier bug where an existing row stored as Movie continued to use Movie parsing after the user switched the selector.

When the user identifies an existing row as a Movie Collection / Box Set:

1. Search TMDb Collections.
2. User selects the collection.
3. Convert the existing physical inventory record into the box-set parent representation without losing copy-level fields.
4. Populate first-class contained movie rows.
5. Remove the item from the pending-review queue.

## Mass Match / Persistent Review

The persistent review page gets the same three-way selector:

- Movie
- TV Box Set
- Movie Collection / Box Set

Corrected-title search uses the selected type.

Choosing a Collection result converts/populates the parent and child movie records exactly as Identify does.

The automatic bulk pass still uses the row's stored media type and does not probe all three TMDb endpoints.

## Database Migration

The migration must be additive and safe for existing v0.3.27 databases.

### Movies table
Add:

`parent_box_set_id INTEGER NULL`

with a foreign-key relationship to the physical box-set table/entity used by v0.3.27.

Index `parent_box_set_id`.

Existing standalone movie rows remain NULL.

### Existing v0.3.27 box-set members
If v0.3.27 stores lightweight member rows in a separate membership table, migrate them into first-class movie rows.

For every existing member:

- preserve TMDb movie ID
- title
- year
- poster / TMDb metadata already stored
- parent box-set relationship
- existing member loan state, if any, translated into the standard movie loan model where possible

The migration must be idempotent and must not create duplicate contained movies on repeated startup.

After successful migration, legacy membership data may remain for compatibility during the release if removing it would make rollback risky, but runtime reads should use the first-class movie rows.

## Data Integrity

A box-set population operation must be transactional.

If member creation fails, Homebuster must not leave a half-populated set.

Re-identifying the same physical set must update/reconcile existing child movies rather than blindly duplicate them.

Uniqueness for contained members should be based on parent + TMDb movie identity when available.

## Collections Naming

Homebuster's existing user-created Collections remain separate from TMDb physical movie box sets.

A TMDb Collection is a source of title identity for a physical box-set parent; it does not automatically create a Homebuster user Collection in v0.3.28.

## API / Android

Server API responses for movies should expose enough parent information for contained items:

- `parent_box_set_id`
- `parent_box_set_name` when applicable
- effective availability
- inherited physical context where useful

Android should remain compatible with the server model. If the Android UI does not yet expose every new box-set member interaction, the API contract must not block adding it later.

No signing secrets are bundled.

## CSV

Normal movie export/import should distinguish contained movies from standalone movies, at minimum via `parent_box_set_id` or a stable parent reference.

Physical box-set export/import remains separate where already implemented.

Import must not silently turn contained children into standalone physical copies.

## Required Regression Coverage

At minimum:

1. Existing Movie-typed row switched to Collection in Identify searches TMDb Collections.
2. Existing Movie-typed row switched to Collection in Review searches TMDb Collections.
3. Selecting a Collection converts/populates a parent and first-class child movie rows.
4. Repeating population does not duplicate children.
5. Contained movie opens through the normal movie-detail route.
6. Contained movie inherits parent physical context for display.
7. Hidden contained movie is still found by search.
8. Library setting exposes contained movies in the grid without duplicates.
9. Individual contained-film loan uses the normal loan model.
10. Active child loan blocks whole-set loan.
11. Whole-set loan blocks child loan.
12. Whole-set loan derives child state as `Loaned with box set`.
13. v0.3.27 lightweight members migrate idempotently to first-class movie rows.
14. Movie and TV behavior outside box sets remains unchanged.
15. No automatic Movie+TV+Collection multi-endpoint search is introduced.

## Release Boundary

v0.3.28 includes:

- first-class contained movie rows
- parent relationship
- normal detail pages for contained films
- normal loan flow for contained films
- box-set inherited physical context
- optional contained-film library grid display
- search behavior
- Identify Collection selector
- Mass Review Collection selector
- v0.3.27 membership migration
- API/schema updates required by the model

Out of scope:

- disc-to-film mapping
- per-contained-film barcode
- per-contained-film shelf location
- automatic creation of Homebuster user Collections from TMDb Collections
- automatic querying of multiple TMDb media endpoints
