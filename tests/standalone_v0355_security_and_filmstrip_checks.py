from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"movie_catalogue/templates/base.html").read_text()
cfg=(ROOT/"movie_catalogue/config.py").read_text()
# non-admin branch must append a compensation cell after logout, not between nav controls
segment=html[html.index('film-cell-libraries'):html.index('mobile-menu-toggle')]
assert '{% if not current_user.is_admin %}<div class="film-cell film-cell-empty"' in segment
assert segment.index('film-cell-logout') < segment.index('{% if not current_user.is_admin %}<div class="film-cell film-cell-empty"')
assert 'REMEMBER_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)' in cfg
assert 'APP_VERSION = "0.3.65"' in cfg
print("v0.3.55 security/filmstrip checks: PASS")
