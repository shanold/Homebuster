from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
assert ".padding(top = 43.dp, horizontal = 10.dp, bottom = 13.dp)" not in m
assert ".padding(start = sideInset, top = topInset, end = sideInset, bottom = bottomInset)" in m
cfg=(R/"movie_catalogue/config.py").read_text()
g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.73"' in cfg
assert 'versionName = "0.3.41"' in g
assert 'versionCode = 33' in g
print("v0.3.66 Compose padding compile regression: PASS")
