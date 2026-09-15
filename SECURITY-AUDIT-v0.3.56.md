# Homebuster v0.3.56 Security Audit

Scope: Flask web app, SQLite access, templates, CSV/file handling, external API boundaries, admin/role checks, mobile API, configuration, and Android source-level credential/network handling.

## Findings

### No critical or high-severity issue identified in this review
- Database writes/reads that include user-controlled values use SQLite bound parameters (`?`). Dynamic `IN (...)` clauses build only placeholder characters from server-side list lengths; values remain bound parameters. The `PRAGMA table_info` interpolation uses internal schema names, not request input.
- Web library routes consistently use login plus library-role enforcement; object lookups generally include the current library ID. Admin routes use the admin-only decorator.
- Mobile API bearer tokens are random, stored as SHA-256 hashes, checked against user `auth_version`, and disabled users are rejected. Mutating library operations verify editor/owner access.
- Flask-WTF CSRF protection covers the browser application. The token-authenticated mobile API is intentionally exempt from cookie-CSRF and requires bearer authentication.
- Jinja templates contain no `|safe` use in the reviewed templates, so normal Jinja autoescaping remains in effect for stored user text.
- Passwords use Werkzeug password hashing. Login errors do not disclose whether a username exists.
- Login `next` redirects reject non-local and scheme-relative targets.
- No request-driven `subprocess`, `os.system`, `eval`, or `exec` execution sink was found.
- Uploads reviewed are parsed as CSV data rather than written to caller-selected filesystem paths. Flask's 16 MiB request limit is enabled.
- Application secrets/API keys are configuration values and were not found embedded in the source package.

### Low: remember-cookie transport setting could diverge from session-cookie security
`SESSION_COOKIE_SECURE` was configurable, but Flask-Login's remember cookie did not explicitly follow it. v0.3.55 sets `REMEMBER_COOKIE_SECURE` from the same environment option. For an Internet-facing HTTPS deployment, set `SESSION_COOKIE_SECURE=true`.

### Deployment note: HTTP remains intentionally supported
Homebuster defaults `SESSION_COOKIE_SECURE` to false because the project is also used directly over LAN HTTP. This is a compatibility choice, not an HTTPS guarantee. Public Internet deployments should terminate TLS and enable secure cookies.

### Defense-in-depth notes
- CSV exports can contain user-entered strings. Spreadsheet applications may interpret cells beginning with formula characters when a CSV is opened. This is not a Homebuster server compromise, but spreadsheet-safe escaping would be reasonable future hardening if exports are routinely opened in Excel/Sheets.
- This was a source audit and regression review, not a penetration test or dependency-CVE scan. Dependency versions should still be kept current and scanned by the deployment/build pipeline.

## v0.3.55 changes
- Non-admin desktop navigation remains contiguous, while one compensating empty film cell is appended after navigation so the 12-cell strip again reaches the right edge.
- `REMEMBER_COOKIE_SECURE` now follows `SESSION_COOKIE_SECURE`.

## Dependency audit and refresh

The production Python dependency pins were reviewed against current upstream release/support information. Gunicorn 23.0.0 was no longer on a supported security-maintenance branch, so this release moves it to 26.2.0. Flask, Flask-WTF, and Requests also received conservative current-version updates. Flask-Login remains 0.6.3 because that is its current release.

Updated production pins:
- Flask 3.1.3
- Flask-Login 0.6.3
- Flask-WTF 1.3.0
- Gunicorn 26.2.0
- Requests 2.34.2

Android dependencies were reviewed separately. No Android dependency was changed in this release because no urgent vulnerability requiring a toolchain/runtime change was identified during the review. Kotlin/Compose toolchain modernization can be handled separately with an actual Android build environment.

This source audit does not replace continuous CVE/dependency scanning of future releases.
