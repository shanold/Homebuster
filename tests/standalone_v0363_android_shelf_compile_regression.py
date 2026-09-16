from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
collection=m[m.index("private fun CollectionDetailScreen"):m.index("private fun LoansScreen")]
shelf=m[m.index("private fun ShelfDetailScreen"):m.index("private fun BarcodeResultScreen")]
assert "shelfViewMode" not in collection
assert "HomebusterShelfFrontCase" not in collection
assert "HomebusterShelfSpine" not in collection
assert "HomebusterMovieCard(group)" in collection
assert "if (shelfViewMode == ShelfViewMode.FRONT)" in shelf
assert "HomebusterShelfFrontCase(group)" in shelf
assert "HomebusterShelfSpine(group)" in shelf
assert "HomebusterShelfCase" not in shelf
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.71"' in cfg
assert 'versionName = "0.3.39"' in gradle
assert 'versionCode = 31' in gradle
print("v0.3.63 shelf compile regression: PASS")
