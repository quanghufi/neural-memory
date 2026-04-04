# Repair Last Conducted Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe maintenance script that previews and repairs invalid `last_conducted` timestamps in Postgres brains.

**Architecture:** Keep database access in one small script and keep repair rules in pure helper functions so tests can verify behavior without touching a real database. The script defaults to dry-run and writes JSON backups before any mutation.

**Tech Stack:** Python, asyncpg, argparse, unittest

---

### Task 1: Add Failing Tests

**Files:**
- Create: `d:\neural-memory\test_repair_last_conducted.py`
- Test: `d:\neural-memory\test_repair_last_conducted.py`

- [ ] **Step 1: Write the failing test**

Write tests that expect:
- `pre2026` rows are selected for repair
- `before-created` rows are selected for repair
- valid rows are ignored
- dry-run mode does not issue updates

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q test_repair_last_conducted.py`
Expected: FAIL because `scripts.repair_last_conducted` does not exist yet

### Task 2: Implement Script

**Files:**
- Create: `d:\neural-memory\scripts\repair_last_conducted.py`
- Modify: `d:\neural-memory\test_repair_last_conducted.py`

- [ ] **Step 1: Write minimal implementation**

Implement:
- env loading from repo `.env`
- policy matching helpers
- dry-run summary output
- JSON backup on `--apply`
- update statements that normalize invalid rows to `created_at`

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest -q test_repair_last_conducted.py`
Expected: PASS

### Task 3: Verify Script CLI

**Files:**
- Modify: `d:\neural-memory\scripts\repair_last_conducted.py`

- [ ] **Step 1: Run preview mode**

Run: `python scripts/repair_last_conducted.py --brain-id default --policy all`
Expected: summary output with no writes

- [ ] **Step 2: Run help output**

Run: `python scripts/repair_last_conducted.py --help`
Expected: usage text with `--apply`, `--brain-id`, and `--policy`
