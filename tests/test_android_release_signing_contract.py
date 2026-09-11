
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "android/app/build.gradle.kts"
IGNORE = ROOT / "android/.gitignore"
EXAMPLE = ROOT / "android/keystore.properties.example"
GUIDE = ROOT / "android/RELEASE_SIGNING.md"

def test_gradle_has_release_signing_config():
    text = GRADLE.read_text()
    assert 'keystore.properties' in text
    assert 'signingConfigs' in text
    assert 'create("release")' in text
    assert 'signingConfig = signingConfigs.getByName("release")' in text
    assert 'GradleException' in text

def test_signing_secrets_are_ignored():
    text = IGNORE.read_text()
    assert 'keystore.properties' in text
    assert '*.jks' in text
    assert '*.keystore' in text

def test_example_contains_only_placeholders():
    text = EXAMPLE.read_text()
    for key in ('storeFile=', 'storePassword=', 'keyAlias=', 'keyPassword='):
        assert key in text
    assert 'CHANGE_ME' in text

def test_release_guide_documents_stable_key_and_build():
    text = GUIDE.read_text()
    assert 'keytool -genkeypair' in text
    assert './gradlew assembleRelease' in text
    assert 'DO NOT' in text
    assert 'same keystore' in text.lower()
