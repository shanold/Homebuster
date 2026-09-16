from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
store=(R/"android/app/src/main/java/com/homebuster/mobile/SessionStore.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
gradle=(R/"android/app/build.gradle.kts").read_text()
assert "lastServerVersion" in store
assert "store.lastServerVersion = detectedVersion" in m
assert "api.status()" in m
assert "currentStatus.serverVersion != savedVersion" in m
assert "Homebuster server was updated" in m
assert "store.clearToken()" in m
assert 'APP_VERSION = "0.3.69"' in cfg
assert 'versionName = "0.3.37"' in gradle
assert 'versionCode = 29' in gradle
print("v0.3.64 server-version reauth checks: PASS")
