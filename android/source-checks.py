from pathlib import Path
root=Path(__file__).parent
src=root/'app/src/main/java/com/homebuster/mobile'
main=(src/'MainActivity.kt').read_text()
theme=(src/'HomebusterTheme.kt').read_text()
comp=(src/'HomebusterComponents.kt').read_text()
scan=(src/'ScannerScreen.kt').read_text()
api=(src/'Api.kt').read_text()
checks={
'root theme':'setContent { HomebusterTheme' in main,
'all web colors': all(x in theme for x in ['101218','191D26','222837','30384A','EEF1F7','9CA6B8','7AA2FF','345FC1','FF6B6B','62D49D','F4C66B']),
'shared grouped movie card':'fun HomebusterMovieCard(group: MovieGroup' in comp and 'HomebusterMovieCard(group)' in main,
'shared panels':'fun HomebusterPanel' in comp and main.count('HomebusterPanel') >= 7,
'screen header':'fun HomebusterScreenHeader' in comp and 'HomebusterScreenHeader("Collections"' in main and 'HomebusterScreenHeader("Loans"' in main,
'no raw ListItem':'ListItem(' not in main,
'back handler preserved':'BackHandler(enabled = screen != Screen.LOGIN && screen != Screen.LIBRARY)' in main,
'scanner themed':'HomebusterScreenHeader("Scan barcode"' in scan and 'HomebusterErrorCard' in scan,
'barcode lookup model':'data class BarcodeLookup' in api and 'val lookup: BarcodeLookup?' in api,
'barcode raw display':'r.product?.productTitle' in main,
'barcode cleaned display':'TMDb search:' in main and 'r.lookup?.let' in main,
'version 0.3.16':'versionName = "0.3.16"' in (root/'app/build.gradle.kts').read_text(),
'system bars':'systemBarsPadding()' in main,
'grouped copies':'data class MovieGroup' in main and 'formatsSummary' in main and 'Physical copies' in main,
'edition display':'lookup.edition' in main and 'lookup.format' in main,
}
checks.update({
'barcode metadata fields': all(x in api for x in ['val language: String?', 'val region: String?', 'val discCount: Int?', 'val distributor: String?']),
'barcode best match': 'val bestMatch: TmdbResult?' in api and 'Best match' in main,
'barcode add workflow': 'Add this copy' in main and 'api.addMovie(' in main,
'barcode distributor transparency': 'Catalog/distributor removed from search:' in main,
})
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(('PASS' if v else 'FAIL'), k)
if failed: raise SystemExit('failed: '+', '.join(failed))
