# Homebuster v0.3.55 Filmstrip + Security Audit Implementation Plan

**Goal:** Restore 12 rendered desktop film cells for both admin and non-admin users without reintroducing a navigation gap, then audit the Flask/SQLite/Android code for practical web security defects and apply only narrow, behavior-preserving fixes.

## Task 1 — Filmstrip
Write a regression that renders/structurally verifies 12 cells in both role paths; fail it; add the non-admin compensation cell at the strip end; pass it.

## Task 2 — Security audit
Review auth/session config, authorization/ownership, SQL construction and parameterization, Jinja escaping, CSRF/state-changing routes, passwords, redirects/URLs, file/path operations, dangerous execution sinks, secrets, external API input handling, and Android credential/network handling. Record concrete findings with file/line evidence. Do not equate stored-input sanitization with SQL safety: verify query parameterization and output-context escaping separately.

## Task 3 — Narrow hardening
For each confirmed high/medium issue that can be fixed without changing intended deployment behavior, write a failing regression first, implement the smallest fix, and rerun. Document findings not changed.

## Task 4 — Release verification
Run security regressions, existing standalone regressions, compileall, Jinja parse, Android source/url checks where available, secret scan, ZIP integrity, and produce v0.3.55 plus audit report.
