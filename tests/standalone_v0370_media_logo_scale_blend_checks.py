from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "val singleLogoHeight = ridgeHeight * .96f" in case
assert "singleLogoHeight" in case and "comboLogoHeight" in case
assert "ColorFilter.tint(Color.White)" in case
assert "graphicsLayer { alpha = .98f }" in case
assert "ridgeHeight * .72f" not in case
cfg=(R/"movie_catalogue/config.py").read_text();g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.71"' in cfg
assert 'versionName = "0.3.39"' in g
assert 'versionCode = 31' in g
print("v0.3.70 media logo scale/blend checks: PASS")
