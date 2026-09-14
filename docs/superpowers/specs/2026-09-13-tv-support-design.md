# Homebuster TV / Box Set Support Design

Homebuster remains an inventory application. A physical item may be a `movie` or `tv`; TV entries represent a series/box set as one physical inventory item rather than seasons/episodes.

Existing database rows migrate to `media_type='movie'`. TMDb searches default to Movie everywhere. TV is queried only when the user explicitly selects TV / Box Set. A matched item's media type is persisted and later metadata refreshes use the corresponding TMDb endpoint.

TMDb-backed grouping identity is `(media_type, tmdb_id)`, preserving physical copies while preventing numeric movie and TV IDs from colliding. Shelves, collections, loans, format, edition, region, disc count, barcode, notes, and status continue to work unchanged for either type.

Web Add, Identify, persistent Match/Repair review, and manual corrected-title search expose a Movie/TV selector. Bulk repair uses each item's stored type. Android carries `media_type` through API models, grouping, display, barcode matching, and add-copy requests; Movie remains the default and TV barcode matching is explicit.

The Match/Repair metadata-refresh checkbox remains off by default and its checkbox is visually inline with its label.
