# Repair Last Conducted Design

**Problem**

Some fibers in the Postgres brain have invalid `last_conducted` timestamps. The bad values fall into two high-risk buckets:

- timestamps before the supported year floor (`2026` for this project)
- timestamps earlier than the fiber `created_at`

These invalid values can distort recency scoring and, in the worst case, trigger retrieval overflow in upstream logic.

**Recommended Approach**

Add a small maintenance script at `scripts/repair_last_conducted.py` instead of mutating data during MCP startup. The script should support dry-run previews, targeted policies, JSON backups before writes, and a safe normalization rule that never invents a timestamp earlier than `created_at`.

**Behavior**

- Default mode is preview-only.
- `--apply` performs updates.
- `--brain-id` selects the target brain and defaults to `default`.
- `--policy` supports `pre2026`, `before-created`, or `all`.
- Every repaired row is normalized to `created_at`.
- On apply, matching rows are backed up to `data/maintenance/` first.

**Testing**

Add focused unit tests for candidate selection and normalization behavior so the script stays safe to re-run.
