from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
api=(R/"android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
store=(R/"android/app/src/main/java/com/homebuster/mobile/SessionStore.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()

assert "Session expired" in m
assert "onSessionExpired" in api
assert "clearToken" in store
assert "ShelfViewMode.FRONT" in m
assert "ShelfViewMode.SPINES" in m
assert "HomebusterShelfFrontCase" in m
assert "Front Covers" in m and "Spines" in m
assert "shelfViewMode" in store
assert "detailsReturnScreen" in m
assert "Screen.SHELF_DETAIL" in m and "Screen.COLLECTION_DETAIL" in m
assert 'APP_VERSION = "0.3.68"' in cfg
assert 'versionName = "0.3.36"' in gradle
assert 'versionCode = 28' in gradle
print("v0.3.62 Android session/shelf/navigation checks: PASS")
