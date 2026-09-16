from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "ridgeHeight" in case
assert "hingeWidth" in case
assert "Color(0x12FFFFFF)" in case
assert "43f / 306f" in case and "10f / 306f" in case and "13f / 306f" in case
assert "3f / 306f" in case
assert "aspectRatio(2f / 3f)" in case
assert "shellRadius * .67f" in case
assert "casePlasticDark" in case and "casePlastic" in case and "caseGlow" in case
assert "Blu-ray Disc" in case
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.72"' in cfg
assert 'versionName = "0.3.40"' in gradle
assert 'versionCode = 32' in gradle
print("v0.3.65 Android/web case parity checks: PASS")
