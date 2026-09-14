# Homebuster Physical Movie Box Sets / TMDb Collections Design

## Status

Approved direction from user discussion. This is an architectural feature because Homebuster currently treats each `movies` row as a physical copy, while a box set is one physical object that contains several independently identifiable movie titles and can be loaned either as a whole or by contained film.

## Goals

Homebuster should make adding a retail movie box set as automatic as possible while preserving inventory truth:

- A box set is one physical inventory object with one barcode, shelf location, format, region, edition/version, language, disc count, notes, and overall loan state.
- TMDb Collection data should populate the contained canonical movie titles automatically.
- By default the main library grid shows one box-set card, not one fake standalone copy per contained film.
- Opening the box-set card shows all contained films and their TMDb artwork/metadata.
- A per-library setting can additionally show contained films in the normal library grid.
- Search always finds contained films, even when they are hidden from the main grid.
- The whole box set can be loaned, or contained films can be loaned individually.
- Homebuster deliberately does not model which exact physical disc contains which movie.
- TMDb request volume remains controlled: one explicitly selected/detected endpoint is queried at a time rather than automatically searching Movie + TV + Collection together.

## Non-goals

- Episode or season tracking for TV.
- Mapping movie titles to physical disc numbers.
- Treating every contained film as though it were a separate retail case/barcode.
- Replacing Homebuster's existing user-created `collections` feature. User collections remain an organizational/tagging feature; TMDb movie collections/physical box sets are a separate concept.

## Approaches Considered

### 1. Create ordinary `movies` rows for every film in the set

This would reuse most existing UI and loan logic, but it makes the database claim that each film is a separate physical copy. Barcode, shelf, format, loan, and copy-count behavior become misleading, and grouping logic would need many exceptions.

**Rejected.** It violates Homebuster's inventory-first model.

### 2. Normalize all titles and physical copies into new generic title/inventory tables

This is the cleanest long-term relational model: canonical titles would be separate from physical containers/copies, and box sets would simply link one inventory item to several titles.

**Deferred.** It would require a broad migration of the working movie, TV, grouping, import/export, loan, API, and Android code. Box-set support does not require rewriting the entire catalogue model now.

### 3. Dedicated physical box-set tables plus contained-title membership rows

A box set is stored separately as a physical inventory object. Its contained films are lightweight membership records containing canonical TMDb identity and display metadata. They are not standalone physical copies. Whole-set and member loans use dedicated loan tables, while existing standalone movie loans remain unchanged.

**Recommended.** This preserves existing movie semantics, minimizes migration risk, and accurately represents ownership.

## Data Model

### `box_sets`

New table representing one physical movie box set.

Suggested fields:

- `id`
- `library_id`
- `barcode`
- `title` — retail/display title, e.g. `Harry Potter 8-Film Collection`
- `tmdb_collection_id` — nullable; populated when matched to a TMDb Collection
- `poster_path` — collection artwork when available
- `format`
- `version` / edition
- `country`
- `language`
- `region`
- `disc_count`
- `notes`
- `shelf_id`
- `status`
- `created_at`
- `updated_at`

The box set owns all physical-copy metadata. Member titles do not duplicate barcode or shelf location.

### `box_set_members`

New table representing canonical films contained by a physical box set.

Suggested fields:

- `id`
- `box_set_id`
- `tmdb_id`
- `title`
- `year`
- `poster_path`
- `position`

A uniqueness rule should prevent the same TMDb movie from being inserted twice into the same box set. These rows are contained-title identities, not standalone physical copies.

### `box_set_loans`

New whole-container loan table, parallel to existing `loans`.

Suggested fields mirror existing loans:

- `id`
- `library_id`
- `box_set_id`
- `borrower_name`
- `phone`
- `loaned_date`
- `returned_date`
- `notes`

Only one active whole-set loan may exist for a box set.

### `box_set_member_loans`

New contained-film loan table.

Suggested fields:

- `id`
- `library_id`
- `box_set_member_id`
- `borrower_name`
- `phone`
- `loaned_date`
- `returned_date`
- `notes`

Only one active individual loan may exist for each contained film.

### Library setting

Add `libraries.show_box_set_members INTEGER NOT NULL DEFAULT 0`.

Default is off. Existing libraries therefore retain a simple physical-inventory grid after migration.

## TMDb Integration

Homebuster will add explicit `Collection / Box Set` search support using TMDb's collection search/details APIs. Existing Movie and TV modes remain separate.

### Search modes

Add/Identify/search modes become:

- Movie
- TV Box Set
- Movie Collection / Box Set

Only the selected mode is queried. Homebuster must not automatically issue Movie, TV, and Collection searches for one user action.

### Scanner/parser behavior

The barcode parser may classify strong retail wording such as:

- `collection`
- `box set` / `boxset`
- `8-film collection`
- `trilogy`
- `quadrilogy`
- `complete movie collection`

as a strong box-set hint. When confidence is high, the UI can preselect Collection / Box Set and make one collection search. The user can override the mode before retrying.

Weak/ambiguous wording should keep Movie as the default. Detection should change the selected endpoint, not fan out API requests.

### Collection result/detail

After the user chooses a TMDb Collection, Homebuster requests that collection's details and receives its movie `parts`.

The confirmation screen shows:

- collection title and artwork
- retail/raw barcode title where applicable
- physical copy metadata parsed from the product title
- contained movie list with title, year, and poster
- checkboxes for each member, selected by default

The member checklist is required because a retail box set may contain only a subset of a broader TMDb franchise collection. The user can deselect titles before saving.

Saving creates one `box_sets` row and the selected `box_set_members` rows in a single transaction.

## Library Grid and Search

### Default grid

`show_box_set_members = 0`:

- standalone movies/TV continue to appear normally
- each physical movie box set appears once as its own card
- member films do not create extra grid cards

A box-set card should visually identify itself and show useful physical summary information such as `8 films`, format, edition, and loan state.

### Optional expanded grid

`show_box_set_members = 1`:

Contained films also appear in the normal grid as virtual/member cards. They must be clearly labeled, e.g. `In box set`, with the parent box-set name. They are not counted as standalone physical copies.

The parent box-set card remains visible.

### Search

Text search always includes `box_set_members.title`, regardless of the library setting. Searching for `Prisoner of Azkaban` should therefore find ownership through the Harry Potter box set even when member cards are hidden from the default grid.

Search results should lead to the contained-film view within the parent box set and make the physical source obvious.

### Counts

Library statistics should distinguish physical inventory from contained titles. The primary physical-item count should not increase merely because a box set has eight member films.

Where useful the UI may show a secondary count such as `142 physical items · 37 contained films`.

## Box-Set Detail Page

Opening a box-set card shows:

- collection artwork/title
- physical metadata (barcode, format, edition, region, language, disc count, shelf, notes)
- overall loan state
- all included films ordered by TMDb collection order
- each film's title, year, poster, and loan state

Owners/editors can edit physical metadata and add/remove/reorder member films. Removing a member must be blocked or explicitly resolved if that member currently has an active individual loan.

A manual member-add flow should permit TMDb Movie search so sets can be corrected when TMDb's collection data does not exactly match the retail package.

## Loan Rules

### Whole-set loan

A whole box set can be loaned only when none of its member films has an active individual loan.

When active:

- the box set shows `Loaned`
- every contained film is effectively unavailable and displays `Loaned with box set`
- individual loan actions are disabled

Returning the whole set makes all members available again. No duplicate child loan rows are created for a whole-set loan; effective member state is derived from the parent loan.

### Individual contained-film loan

A member film can be loaned individually only when the whole box set is not currently loaned.

When active:

- that member shows `Loaned individually`
- other members remain available
- the parent box set shows an `Incomplete / member loaned` indication
- the whole-set loan action is disabled until all individual member loans are returned

### Disc mapping

Homebuster intentionally ignores which title resides on which exact physical disc. A contained film is treated as independently loanable for inventory simplicity even if a particular retail edition puts multiple films on one disc.

## Existing User Collections

The current `collections` and `movie_collections` tables remain unchanged and continue to represent user-created organization groups.

Terminology in the UI should avoid conflating them:

- **Collection** (existing Homebuster feature): user-defined organizational grouping
- **Movie Box Set** / **TMDb Collection**: one physical retail container with several movie titles

A box set may itself optionally be assigned to user-created organizational collections in a later extension, but this is not required for the first implementation.

## Import / Export

CSV export should preserve box sets and their member list without flattening members into fake standalone copies.

Because the existing movie CSV format is one row per physical movie copy, box sets should either:

1. receive a separate box-set CSV export/import, or
2. extend the export format with record-type rows plus a documented member encoding.

The implementation plan should prefer a separate box-set CSV for the first release because it is easier to validate and does not destabilize existing movie imports.

## API / Android

The server API should expose box sets as first-class physical items rather than synthesizing them as movies.

Minimum API concepts:

- list/search box sets
- box-set detail with member films
- collection lookup/search
- create box set from selected TMDb members
- whole-set loan/return
- member loan/return
- library setting controlling whether member titles are included in normal browsing

Android should eventually mirror the web behavior:

- box-set card in library
- open card to view members
- contained-title search
- explicit Movie / TV / Collection scanner mode
- whole-set and individual member loan state

The web/server implementation should be verified first before requiring a newly signed Android build, preserving the current workflow of stabilizing server behavior before mobile release packaging.

## Migration and Compatibility

Migration is additive:

- create new box-set/member/loan tables
- add `libraries.show_box_set_members` with default `0`
- do not rewrite existing `movies`, `loans`, `collections`, or `movie_collections` rows

Existing databases should start normally after migration with no visible behavior change until a box set is added.

Deletion should cascade from a box set to its member rows only after active loans are resolved. Loan history should not be silently lost; deletion should either be blocked when loan history exists or require the same kind of explicit destructive confirmation used elsewhere in Homebuster.

## Failure Handling

- If TMDb collection lookup fails, the user remains on the confirmation/search flow and can retry or add the box set manually.
- If a TMDb collection has no parts, Homebuster can still create a manual box set and let the user add members later.
- If one selected member lacks a poster/year, the box set still saves; missing display metadata must not abort the transaction.
- Database creation of the box set and selected members should be transactional to prevent half-created sets.
- Duplicate barcode behavior should follow Homebuster's existing copy/barcode policy rather than invent a box-set-specific rule.

## Testing Strategy

Implementation should be test-driven and include at least:

- additive migration on an existing v0.3.26 database
- TMDb Collection search uses only `/search/collection`
- Movie and TV modes remain unchanged and do not query collection endpoints
- strong box-set wording selects/produces Collection-mode candidates without issuing multiple endpoint searches
- collection details map `parts` into deterministic member order
- saving a collection creates one physical box set and selected members only
- hidden-member default grid behavior
- optional member-card grid behavior
- search finds hidden contained films
- physical counts do not count member rows as separate copies
- whole-set loan blocks individual loans
- individual member loan blocks whole-set loan
- returning loans restores the correct effective availability
- existing standalone movie/TV loan tests remain green
- existing manual Homebuster collections remain unchanged
- CSV movie import/export regressions remain green; box-set export/import gets dedicated tests if included in the first release
- mobile/API source contract tests for new box-set response types before Android UI work

## First-Release UX Example

Scanning `Harry Potter 8-Film Collection Blu-ray`:

1. Parser recognizes strong box-set wording and preselects **Collection / Box Set**.
2. Homebuster performs one TMDb Collection search for `Harry Potter`.
3. User selects **Harry Potter Collection**.
4. Homebuster fetches the collection details and displays the eight member films.
5. All films are selected by default; the user can remove any that are not in the physical package.
6. Parsed physical metadata such as Blu-ray, edition, region, and disc count is shown for confirmation.
7. Save creates one physical Harry Potter box set plus eight contained-title membership rows.
8. The default library grid shows one Harry Potter box-set card.
9. Searching for `Prisoner of Azkaban` finds that movie inside the set.
10. The owner can loan the whole set, or loan `Prisoner of Azkaban` individually.
