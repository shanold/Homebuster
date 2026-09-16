from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[1]
res=R/"android/app/src/main/res/drawable-nodpi"
for f in ["media_logo_dvd_video.png","media_logo_bluray.png","media_logo_uhd_bluray.png"]:
    im=Image.open(res/f).convert("RGBA")
    alpha=im.getchannel("A")
    assert alpha.getextrema()[0] == 0, f"{f}: background is not transparent"
    assert alpha.getbbox() is not None
m=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
case=m[m.index("private fun HomebusterShelfFrontCase"):m.index("private fun HomebusterShelfSpine")]
assert "val singleLogoHeight = ridgeHeight * .96f" in case
assert "val comboLogoHeight = ridgeHeight * .88f" in case
assert "singleLogoHeight" in case
assert "comboLogoHeight" in case
assert "Modifier.height(if (" in case
assert "ColorFilter.tint(Color.White)" in case
cfg=(R/"movie_catalogue/config.py").read_text(); g=(R/"android/app/build.gradle.kts").read_text()
assert 'APP_VERSION = "0.3.73"' in cfg
assert 'versionName = "0.3.41"' in g
assert 'versionCode = 33' in g
print("v0.3.71 transparent/large media-logo checks: PASS")
