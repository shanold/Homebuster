from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android/app/src/main/java/com/homebuster/mobile'

class V035SourceContract(unittest.TestCase):
    def test_android_has_human_friendly_401_and_system_back_navigation(self):
        text = (ANDROID / 'MainActivity.kt').read_text()
        self.assertIn('Incorrect username or password', text)
        self.assertIn('BackHandler', text)
        self.assertIn('navigateBack', text)

    def test_session_store_uses_keystore_not_deprecated_security_crypto(self):
        text = (ANDROID / 'SessionStore.kt').read_text()
        self.assertIn('AndroidKeyStore', text)
        self.assertNotIn('EncryptedSharedPreferences', text)
        self.assertNotIn('MasterKey', text)
        gradle = (ROOT / 'android/app/build.gradle.kts').read_text()
        self.assertNotIn('androidx.security:security-crypto', gradle)

    def test_branding_assets_are_wired_for_web_and_android(self):
        base = (ROOT / 'movie_catalogue/templates/base.html').read_text()
        manifest = (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text()
        self.assertIn('favicon.png', base)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertTrue((ROOT / 'movie_catalogue/static/favicon.png').exists())
        self.assertTrue((ROOT / 'android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png').exists())

if __name__ == '__main__':
    unittest.main()
