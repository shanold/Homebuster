from pathlib import Path

R = Path(__file__).resolve().parents[1]

dev = R / "DEVELOPER.md"
assert dev.exists(), "DEVELOPER.md must provide a human-readable code map"
text = dev.read_text(encoding="utf-8")
for heading in (
    "# Homebuster Developer Guide",
    "## Architecture at a glance",
    "## Database model",
    "## Authentication and authorization",
    "## Media identification pipeline",
    "## Libraries, shelves, loans, and TV moves",
    "## Smart Collections and box sets",
    "## Android client",
    "## Security boundaries and secrets",
    "## Where to make common changes",
):
    assert heading in text, f"missing developer-guide section: {heading}"

markers = {
    "movie_catalogue/__init__.py": "# Security boundary: browser sessions and API bearer tokens are deliberately separate.",
    "movie_catalogue/db.py": "# Schema map:",
    "movie_catalogue/permissions.py": "# Library access is role-based and is checked again on each protected request.",
    "movie_catalogue/barcode_matching.py": "# Shared barcode-to-TMDb matching logic used by both web and mobile flows.",
    "movie_catalogue/smart_collections.py": "# Smart Collections never invent membership from titles; TMDb collection identity is authoritative.",
    "movie_catalogue/libraries.py": "# TV organizer rule: detection is automatic, but moving inventory always requires explicit review.",
    "movie_catalogue/catalog.py": "# Catalog responsibilities:",
    "movie_catalogue/mobile_api.py": "# Mobile API security model:",
    "android/app/src/main/java/com/homebuster/mobile/Api.kt": "// API contract mirror:",
    "android/app/src/main/java/com/homebuster/mobile/SessionStore.kt": "// Persist only connection/session preferences here; business data remains server-authoritative.",
    "android/app/src/main/java/com/homebuster/mobile/MainActivity.kt": "// Navigation/state map:",
}
for rel, marker in markers.items():
    body = (R / rel).read_text(encoding="utf-8")
    assert marker in body, f"missing readability marker in {rel}"

cfg = (R / "movie_catalogue/config.py").read_text(encoding="utf-8")
gradle = (R / "android/app/build.gradle.kts").read_text(encoding="utf-8")
assert 'APP_VERSION = "0.3.73"' in cfg
assert 'versionName = "0.3.41"' in gradle
assert 'versionCode = 33' in gradle
print("v0.3.73 readability/documentation checks: PASS")
