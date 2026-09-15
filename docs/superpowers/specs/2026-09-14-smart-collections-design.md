# Homebuster Smart Collections Design

Date: 2026-09-14
Target release: v0.3.41
Baseline: v0.3.40
Status: Approved in-chat design; awaiting written-spec review

## Goal

Add TMDb-backed Smart Collection recommendations to Homebuster without turning Collections into a second inventory system or causing excessive TMDb traffic. Smart Collections help users organize movies they already own into official franchise/series groupings. They never add unowned titles to the user's library.

This release also updates the header wordmark to uppercase HOMEBUSTER with the existing purple block style and a subtle yellow glow.

## Core Principles

1. A Smart Collection is ultimately a normal Homebuster organizational Collection.
2. TMDb official collection membership is authoritative; Homebuster does not infer franchises from title similarity.
3. Recommendations are suggestions only. Homebuster does not create a Smart Collection until the user approves it, except when the user explicitly adds or identifies a physical Movie Collection / Box Set.
4. Collections contain only movie records the user actually owns.
5. Physical box sets remain separate physical inventory objects. Their contained first-class movie records may belong to an organizational Collection; the physical parent box-set card does not.
6. TMDb requests are cached and throttled. Opening the Collections page repeatedly must not repeatedly query TMDb.
7. Smart Collection settings and dismissals are library-scoped.

## Recommendation Eligibility

A TMDb movie collection is eligible to be suggested when all of the following are true:

- Smart Collections are enabled for the library.
- The library owns at least 2 distinct movies in the TMDb collection.
- The owned count is at least 50% of the collection's released movies.
- The collection has not already been approved/created as a TMDb-backed Homebuster Collection.
- The suggestion has not been dismissed, unless the user has enabled Show dismissed collections.

Ownership counts distinct TMDb movie IDs rather than physical rows, so multiple copies of the same film do not inflate completion.

Unreleased/upcoming TMDb members do not count in the denominator used for recommendation eligibility. They are not inserted into Homebuster and do not make a previously complete collection appear incomplete merely because a future film was announced.

Example behavior:

- 2 of 3 owned: suggest.
- 2 of 4 owned: suggest.
- 2 of 9 owned: do not suggest.
- 5 of 9 owned: suggest.

## Collections Page UX

The existing Collections page gains a Smart Collection recommendation section above the normal collection list when the feature is enabled and eligible suggestions exist.

A recommendation shows:

- official TMDb collection name;
- owned/released count, e.g. `5 of 9 owned`;
- Create Collection action;
- Not interested action.

Create Collection creates or reuses the corresponding Homebuster organizational Collection, associates it with the TMDb collection ID, and links every currently owned matching movie.

Not interested persistently dismisses that TMDb collection for that library.

The page includes a Show dismissed collections toggle. When enabled, dismissed suggestions are visible and can be restored so they may be suggested/created again.

Library Settings includes a Smart Collections enable/disable setting. Disabling it hides recommendations and stops Smart Collection refresh work. It does not delete or alter collections that were already created.

## Approved Smart Collection Behavior

An approved Smart Collection remains a normal Homebuster Collection and uses the existing Collection views/APIs wherever possible.

It additionally stores its TMDb collection identity. When a movie is subsequently added or identified and TMDb says it belongs to an already-approved collection in that library, Homebuster automatically links the owned movie to that Homebuster Collection. No second approval is required.

This auto-link occurs during the existing add/identify metadata flow and does not require a separate polling request for that movie.

Removing a movie from inventory removes that owned record in the normal way. Smart Collections never synthesize placeholder movie rows for titles the user does not own.

## Physical Movie Collections / Box Sets

Explicitly adding or identifying an item as Movie Collection / Box Set is considered direct user intent and bypasses the Smart Collection recommendation threshold.

After TMDb collection identification:

1. Homebuster creates or reuses the organizational Collection associated with that TMDb collection.
2. The physical box set remains the physical parent inventory object.
3. The contained first-class movie records are linked to the organizational Collection.
4. The physical parent box-set card itself is not linked as a movie member of that organizational Collection.
5. If the TMDb-backed Homebuster Collection already exists, it is reused rather than duplicated.

This behavior must apply consistently to web Add/Identify/Review/Match paths and the existing Android collection/box-set add path where those paths already create physical movie box sets.

## Data Model

### libraries

Add:

- `smart_collections_enabled INTEGER NOT NULL DEFAULT 1`

The setting is per library. Existing libraries migrate enabled.

### collections

Extend the existing table with nullable TMDb backing metadata:

- `tmdb_collection_id INTEGER NULL`
- `tmdb_collection_name TEXT NULL` if useful for stable display/cache behavior
- `tmdb_last_refreshed_at TEXT NULL`

A uniqueness rule should prevent more than one TMDb-backed organizational Collection for the same `(library_id, tmdb_collection_id)` while leaving manual collections unaffected.

### Movie collection-membership cache

Persist enough TMDb membership metadata to compute suggestions locally instead of re-fetching each movie every time Collections is opened. The implementation plan may choose either movie columns or a focused cache table, but the externally observable behavior is fixed:

- map a TMDb movie ID to its TMDb collection ID/name when known;
- distinguish checked-with-no-collection from never-checked where needed;
- record refresh age;
- avoid duplicate network work for multiple physical copies of the same TMDb movie.

A focused cache table is preferred if it keeps TMDb-derived metadata separate from physical inventory state and avoids duplicating identical metadata across copies.

### Dismissals

Add a library-scoped dismissal table keyed by `(library_id, tmdb_collection_id)` with a dismissal timestamp. Dismissal survives sessions and server restarts. Restoring a dismissed suggestion deletes/clears that dismissal state.

## TMDb Metadata Capture and Refresh

Newly identified/added movies should capture `belongs_to_collection` metadata from movie-detail responses when that data is already available. Do not make a redundant TMDb request when the current response already contains the required relationship.

Existing libraries need a backfill path for movies whose collection membership is not cached. Backfill must be incremental/batched rather than issuing a large request burst on every Collections page load.

Known TMDb collection details may be refreshed at most once per 24-hour period. The purpose is to keep official membership and released-member totals current. This refresh is silent housekeeping:

- no new-release notification;
- no popup;
- no unowned movie creation;
- no repeated refresh caused by revisiting the page within the 24-hour window.

If TMDb is unavailable, Homebuster uses its cached information and leaves the refresh eligible for a later attempt. A TMDb failure must not prevent the user from viewing or managing existing Collections.

No Movie + TV + Collection endpoint fan-out is introduced.

## Existing Library Backfill UX

Smart Collections should become useful for existing collections without requiring users to re-identify their library. Homebuster may process uncached, TMDb-matched movie IDs in bounded batches when Smart Collections are used, with progress/state persisted between requests.

The implementation must avoid a single page request generating an unbounded number of TMDb calls. If the existing bulk-progress infrastructure is a good fit, reuse its pattern rather than introducing a background-worker subsystem solely for this feature.

Until backfill completes, recommendations may be incomplete; the UI should not falsely claim that the scan is complete if unchecked movies remain.

## Manual Collections and Deduplication

Manual collections continue to work exactly as before.

If a user already has a manually named collection that appears to have the same name as a TMDb collection, Homebuster must not silently assume identity from the name alone. TMDb identity should be attached only through an explicit Smart Collection approval/physical box-set flow, or an explicit future user action designed for linking.

Once a collection has a `tmdb_collection_id`, that ID—not the display name—is used for automatic membership and deduplication.

## Android Scope

Smart Collection recommendation/dismissal UI is web-first for v0.3.41. Android does not need a new recommendation screen in this release.

Existing Android collection APIs should continue to see approved Smart Collections as normal Homebuster Collections. Android's existing Movie Collection / Box Set add path must receive the server-side automatic organizational-collection behavior, so adding a physical collection from Android produces the same database result as the web path.

Android versionName/versionCode remain unchanged unless a separate Android release is explicitly requested.

## Header Wordmark

Change the film-strip header text to `HOMEBUSTER` in all capitals.

Retain the bold/blocky purple visual introduced in v0.3.40. Add a small yellow glow as a restrained text-shadow layer. The glow should be visible as a warm edge/accent, not a large fuzzy neon halo.

This change applies to the header wordmark. It does not redesign the existing login-page image asset in this release.

## Error Handling

- TMDb lookup/refresh failures do not block Collections page rendering.
- Cached Smart Collection data remains usable during TMDb outages.
- Approve is idempotent: repeated requests must not create duplicate collections or duplicate membership links.
- Dismiss/restore is idempotent.
- Automatic membership linking uses existing collection/member uniqueness protections and must not create duplicate links.
- Migration must preserve all existing manual collections, physical box sets, and collection memberships.

## Testing Requirements

Add standalone regressions before implementation for at least:

- 50% + minimum-two eligibility rules;
- released-member denominator excludes upcoming movies;
- duplicate physical copies count once toward ownership percentage;
- dismissed suggestions hidden by default and visible when requested;
- restore makes a suggestion eligible again;
- Smart Collections disabled prevents suggestions/refresh behavior;
- approval creates/reuses one TMDb-backed normal Collection;
- approval links only owned matching movie rows;
- future identified owned movie auto-links to approved collection;
- physical Movie Collection / Box Set automatically creates/reuses the organizational collection and links child movies, not the parent;
- repeated approval/add paths do not duplicate collections or memberships;
- 24-hour refresh throttle;
- TMDb failure falls back to cached state;
- existing manual collections remain unaffected;
- header renders `HOMEBUSTER` and includes the subtle glow styling.

Run the project's normal verification suite: standalone regressions, Python compileall, Jinja parsing, URL-reference checks, Android source/url checks, signing-secret scan, and ZIP integrity. Full Flask pytest and Android Gradle build should only be claimed if their required runtime/wrapper is actually available.

## Non-Goals for v0.3.41

- No automatic addition of movies the user does not own.
- No notifications about new/upcoming franchise releases.
- No TV-series Smart Collections.
- No title-heuristic franchise guessing.
- No background-worker/queue subsystem solely for Smart Collections.
- No Android Smart Collection recommendation UI.
- No redesign of physical box-set semantics or loan behavior.
- No login-page logo redesign.
