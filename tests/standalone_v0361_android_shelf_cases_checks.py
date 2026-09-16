from pathlib import Path
R=Path(__file__).resolve().parents[1]
main=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert "HomebusterShelfCase" in main
assert "vertical-rl" not in main  # Android implementation, not copied CSS
assert '"Blu-ray"' in main and '"4K UHD"' in main and '"DVD"' in main
assert "ShelfDetailScreen" in main
section=main[main.index("private fun ShelfDetailScreen"):]
assert "HomebusterShelfCase(group)" in section
assert "HomebusterMovieCard(group)" not in section.split("@Composable",1)[0]
assert 'APP_VERSION = "0.3.61"' in cfg
assert 'versionName = "0.3.29"' in gradle
assert 'versionCode = 21' in gradle
print("v0.3.61 Android shelf case checks: PASS")
