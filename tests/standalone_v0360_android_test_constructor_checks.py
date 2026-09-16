from pathlib import Path
R=Path(__file__).resolve().parents[1]
test=(R/"android/app/src/test/java/com/homebuster/mobile/MovieTest.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert "Movie(" in test
assert "id = 1" in test
assert "libraryId = 1" in test
assert 'mediaType = "movie"' in test
assert 'title = "Alien"' in test
assert 'posterPath = "/abc.jpg"' in test
assert 'format = "Blu-ray"' in test
assert 'watched = false' in test
assert 'APP_VERSION = "0.3.71"' in cfg
assert 'versionName = "0.3.39"' in gradle
assert 'versionCode = 31' in gradle
print("v0.3.60 Android constructor regression: PASS")
