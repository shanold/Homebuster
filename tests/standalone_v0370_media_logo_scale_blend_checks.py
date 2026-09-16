from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "val logoHeight = ridgeHeight * .90f" in case
assert "Modifier.height(logoHeight)" in case
assert "ColorFilter.tint(Color.White)" in case
assert "graphicsLayer { alpha = .98f }" in case
assert "ridgeHeight * .72f" not in case
cfg=(R/"movie_catalogue/config.py").read_text();g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.70"' in cfg
assert 'versionName = "0.3.38"' in g
assert 'versionCode = 30' in g
print("v0.3.70 media logo scale/blend checks: PASS")
