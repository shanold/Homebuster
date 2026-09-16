from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "HomebusterCaseTopRidge" in case
assert "HomebusterCaseHinge" in case
assert "HomebusterCasePlasticOverlay" in case
assert "start = 10.dp" in case and "top = 43.dp" in case and "end = 10.dp" in case and "bottom = 13.dp" in case
assert "padding(3.dp)" in case
assert "aspectRatio(2f / 3f)" in case
assert "RoundedCornerShape(12.dp, 12.dp, 8.dp, 8.dp)" in case
assert "casePlasticDark" in case and "casePlastic" in case and "caseGlow" in case
assert "HomebusterCaseFormatLogo" in case
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.66"' in cfg
assert 'versionName = "0.3.34"' in gradle
assert 'versionCode = 26' in gradle
print("v0.3.65 Android/web case parity checks: PASS")
