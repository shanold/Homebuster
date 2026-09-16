from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
res=R/"android/app/src/main/res/drawable-nodpi"
for f in ["media_logo_dvd_video.png","media_logo_bluray.png","media_logo_uhd_bluray.png"]:
    assert (res/f).exists(), f
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
for ref in ["R.drawable.media_logo_dvd_video","R.drawable.media_logo_bluray","R.drawable.media_logo_uhd_bluray"]:
    assert ref in case
assert "upload.wikimedia.org" not in case
cfg=(R/"movie_catalogue/config.py").read_text(); g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.73"' in cfg
assert 'versionName = "0.3.41"' in g
assert 'versionCode = 33' in g
print("v0.3.69 bundled media-logo checks: PASS")
