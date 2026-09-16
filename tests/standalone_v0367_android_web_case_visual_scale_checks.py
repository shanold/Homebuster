from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "BoxWithConstraints" in case
assert "val caseWidth = maxWidth" in case
assert "val topInset = caseWidth * (43f / 306f)" in case
assert "val sideInset = caseWidth * (10f / 306f)" in case
assert "val bottomInset = caseWidth * (13f / 306f)" in case
assert "val ridgeTop = caseWidth * (7f / 306f)" in case
assert "val ridgeHeight = caseWidth * (29f / 306f)" in case
assert 'Text("DVD")' not in case
assert "Blu-ray Disc" in case
assert "DVD Video" in case
assert "Ultra HD Blu-ray" in case
cfg=(R/"movie_catalogue/config.py").read_text()
g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.67"' in cfg
assert 'versionName = "0.3.35"' in g
assert 'versionCode = 27' in g
print("v0.3.67 Android web-case visual scale checks: PASS")
