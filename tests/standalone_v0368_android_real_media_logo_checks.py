from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "R.drawable.media_logo_dvd_video" in case
assert "R.drawable.media_logo_bluray" in case
assert "R.drawable.media_logo_uhd_bluray" in case
assert "painterResource(" in case
assert 'Text("DVD Video"' not in case
assert 'Text("Blu-ray Disc"' not in case
assert 'Text("Ultra HD Blu-ray"' not in case
cfg=(R/"movie_catalogue/config.py").read_text()
g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.72"' in cfg
assert 'versionName = "0.3.40"' in g
assert 'versionCode = 32' in g
print("v0.3.68 real media-logo checks: PASS")
