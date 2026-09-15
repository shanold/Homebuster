# Responsive Filmstrip Header Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive filmstrip header whose navigation is intrinsically aligned to real shrinking film cells.

**Architecture:** Use one CSS grid spanning the viewport for desktop film cells. Navigation items occupy grid cells and each cell draws its own divider; mobile switches to the existing compact menu.

**Tech Stack:** Flask/Jinja, CSS, vanilla JavaScript

**Spec:** `docs/superpowers/specs/2026-09-15-responsive-filmstrip-header-design.md`

## Global Constraints
- Server version becomes 0.3.48.
- Do not change the approved house or HOMEBUSTER wordmark assets.
- Preserve v0.3.45 mobile dropdown behavior.

---

### Task 1: Responsive film cell grid
**Files:** `movie_catalogue/templates/base.html`, `movie_catalogue/static/styles.css`, `tests/standalone_v0348_responsive_filmstrip_grid_checks.py`
- [ ] Write a failing structural regression test for real responsive cells.
- [ ] Replace desktop fixed-coordinate navigation with a viewport grid.
- [ ] Make each nav item occupy and center within one cell.
- [ ] Draw dividers from cell borders rather than separate fixed coordinates.
- [ ] Verify mobile switches to the compact menu.

### Task 2: Version and verification
**Files:** `movie_catalogue/config.py`
- [ ] Set version to 0.3.48.
- [ ] Run focused regression, compile, template parse, Android source checks, and ZIP integrity.
