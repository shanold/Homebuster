# Homebuster Android UI and Barcode Lookup Design

## Goal
Make the Android companion feel like the Homebuster web application while remaining phone-native, and improve barcode-to-TMDb matching without losing the original product title shown to the user.

## Android visual design
The Android app will reuse the web application's visual language rather than Material defaults: background `#101218`, primary panel `#191d26`, secondary panel `#222837`, border `#30384a`, text `#eef1f7`, muted text `#9ca6b8`, blue accent `#7aa2ff`, primary blue `#345fc1`, danger red `#ff6b6b`, success green `#62d49d`, and warning gold `#f4c66b`.

Screens remain native Compose layouts. The library becomes the visual anchor: a compact branded top bar, search field, clear navigation actions, and a poster-first adaptive grid with bordered 14dp cards matching the web catalogue. Metadata is visually secondary to title/poster. Collections and Loans use the same panel/card treatment instead of bare Material ListItems. Details use a clear app bar/back action, poster, title, metadata chips, and readable sections. Scanner and barcode results use the same shell and card styling.

System Back and visible back navigation retain the behavior introduced in v0.3.5.

## Component structure
`MainActivity.kt` continues to own screen state and navigation, but shared Homebuster theme values and reusable UI pieces move into focused Compose files so the redesign does not turn MainActivity into a larger monolith.

- `HomebusterTheme.kt`: colors, Material color scheme, shapes, typography defaults.
- `HomebusterComponents.kt`: app header, screen header/back action, panel/card primitives, metadata chips, empty/error states, movie poster card.
- `MainActivity.kt`: screen routing and screen composition.
- `ScannerScreen.kt`: scanner behavior plus Homebuster-styled scanner chrome.

No server-side web styling is changed by the Android redesign.

## Barcode sanitization
The barcode provider's original title remains untouched in the API response and Android display. A separate server-side sanitizer derives TMDb search inputs.

The sanitizer will:
- normalize whitespace;
- remove bracketed/parenthesized media tokens such as `[DVD]`, `(DVD)`, `[Blu-ray]`, `(Blu-ray)`, `[4K UHD]`, `(Ultra HD)`;
- remove common standalone packaging/media tokens such as DVD, Blu-ray/Blu Ray, 4K UHD, Ultra HD, UHD, Digital Copy, Combo Pack when they appear as product qualifiers;
- extract a plausible four-digit movie year (1900 through the current year plus one) from trailing/bracketed qualifier text and pass it separately to TMDb;
- avoid stripping meaningful title words merely because they resemble edition terminology;
- preserve punctuation that belongs to the movie title;
- return both `clean_title` and optional `year`.

Lookup order is:
1. cleaned title plus extracted year when a year exists;
2. cleaned title without year when the first search has no results;
3. if cleaning produces an unusable/empty title, fall back to the original provider title.

The raw provider title remains visible in the barcode-result screen, while the result also clearly indicates the cleaned movie search title used for TMDb.

## API/data flow
`GET /api/v1/barcodes/<upc>` first checks the user's Homebuster library as before. For an unknown barcode it retrieves the product title, calls the sanitizer, performs the TMDb fallback sequence, and returns the raw product plus lookup metadata and TMDb candidates. No API key is moved to Android.

The response adds lookup metadata in a backwards-compatible object, e.g. `lookup: {"title":"Spider-Man","year":2002}`. Existing `product` and `tmdbResults` fields remain.

## Error handling
A barcode that cannot be identified still gets the existing human-readable not-found state. If the product provider returns a title but TMDb finds no candidate, Android shows the product title, the cleaned search term, and “No TMDb matches found” rather than implying the barcode itself failed.

Network/API errors continue through the existing friendly error mapping.

## Testing
Server tests cover representative title cleanup including `Spider-Man [DVD] 2002`, `Spider-Man (Blu-ray)`, `Spider-Man 4K UHD`, whitespace, titles without media qualifiers, and year extraction. API tests verify raw product title preservation and lookup metadata.

Android source/build checks verify the Homebuster theme is applied at the app root, shared components are used by the major screens, barcode result renders raw and cleaned titles, and existing Back behavior remains. A full Android Gradle build is the final compile check when Gradle/Android SDK tooling is available.
