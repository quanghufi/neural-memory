"""Preview and repair invalid fiber last_conducted timestamps."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg


YEAR_FLOOR = 2026
POLICIES = ("pre2026", "before-created", "all")


def load_local_env(env_path: Path | None = None) -> dict[str, str]:
    env_path = env_path or Path(__file__).resolve().parent.parent / ".env"
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        loaded[key.strip()] = value.strip()
    return loaded


def normalize_last_conducted(
    created_at: datetime,
    last_conducted: datetime | None,
    year_floor: int = YEAR_FLOOR,
) -> datetime | None:
    if last_conducted is None:
        return None
    if last_conducted.year < year_floor:
        return created_at
    if last_conducted < created_at:
        return created_at
    return last_conducted


def _repair_reason(
    created_at: datetime,
    last_conducted: datetime | None,
    policy: str,
    year_floor: int,
) -> str | None:
    if last_conducted is None:
        return None

    if policy in ("pre2026", "all") and last_conducted.year < year_floor:
        return "pre2026"
    if policy in ("before-created", "all") and last_conducted < created_at:
        return "before-created"
    return None


def find_candidates(
    rows: list[dict[str, Any]],
    policy: str = "all",
    year_floor: int = YEAR_FLOOR,
) -> list[dict[str, Any]]:
    if policy not in POLICIES:
        raise ValueError(f"Unsupported policy: {policy}")

    candidates: list[dict[str, Any]] = []
    for row in rows:
        created_at = row["created_at"]
        last_conducted = row.get("last_conducted")
        reason = _repair_reason(created_at, last_conducted, policy, year_floor)
        if reason is None:
            continue

        candidate = dict(row)
        candidate["reason"] = reason
        candidate["normalized_last_conducted"] = normalize_last_conducted(
            created_at=created_at,
            last_conducted=last_conducted,
            year_floor=year_floor,
        )
        candidates.append(candidate)
    return candidates


def _serialize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in candidate.items():
        if isinstance(value, datetime):
            serialized[key] = value.astimezone(UTC).isoformat()
        else:
            serialized[key] = value
    return serialized


def write_backup(
    candidates: list[dict[str, Any]],
    backup_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    backup_dir = backup_dir or Path("data/maintenance")
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(UTC)
    backup_path = backup_dir / (
        f"last_conducted_backup_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    backup_path.write_text(
        json.dumps([_serialize_candidate(candidate) for candidate in candidates], indent=2),
        encoding="utf-8",
    )
    return backup_path


async def repair_candidates(
    conn: Any,
    candidates: list[dict[str, Any]],
    apply: bool,
) -> dict[str, Any]:
    if not apply or not candidates:
        return {
            "candidate_count": len(candidates),
            "updated_count": 0,
        }

    sql = "UPDATE fibers SET last_conducted = $1 WHERE id = $2"
    args = [
        (candidate["normalized_last_conducted"], candidate["id"])
        for candidate in candidates
    ]
    await conn.executemany(sql, args)
    return {
        "candidate_count": len(candidates),
        "updated_count": len(args),
    }


async def fetch_rows(conn: asyncpg.Connection, brain_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, brain_id, created_at, last_conducted
        FROM fibers
        WHERE brain_id = $1
          AND last_conducted IS NOT NULL
        ORDER BY last_conducted ASC, id ASC
        """,
        brain_id,
    )
    return [dict(row) for row in rows]


def build_summary(
    brain_id: str,
    policy: str,
    candidates: list[dict[str, Any]],
    apply: bool,
    backup_path: Path | None,
    sample_limit: int,
) -> dict[str, Any]:
    return {
        "brain_id": brain_id,
        "policy": policy,
        "apply": apply,
        "candidate_count": len(candidates),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "samples": [
            {
                "id": candidate["id"],
                "reason": candidate["reason"],
                "created_at": candidate["created_at"].astimezone(UTC).isoformat(),
                "last_conducted": candidate["last_conducted"].astimezone(UTC).isoformat(),
                "normalized_last_conducted": candidate["normalized_last_conducted"]
                .astimezone(UTC)
                .isoformat(),
            }
            for candidate in candidates[:sample_limit]
        ],
    }


async def run_repair(
    database_url: str,
    brain_id: str,
    policy: str,
    apply: bool,
    backup_dir: Path,
    year_floor: int,
    sample_limit: int,
) -> dict[str, Any]:
    conn = await asyncpg.connect(database_url)
    try:
        rows = await fetch_rows(conn, brain_id)
        candidates = find_candidates(rows, policy=policy, year_floor=year_floor)
        backup_path = None
        if apply and candidates:
            backup_path = write_backup(candidates, backup_dir=backup_dir)
        result = await repair_candidates(conn, candidates=candidates, apply=apply)
        result.update(
            build_summary(
                brain_id=brain_id,
                policy=policy,
                candidates=candidates,
                apply=apply,
                backup_path=backup_path,
                sample_limit=sample_limit,
            )
        )
        return result
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or repair invalid fiber last_conducted timestamps.",
    )
    parser.add_argument("--brain-id", default="default", help="Target brain id.")
    parser.add_argument(
        "--policy",
        choices=POLICIES,
        default="all",
        help="Which invalid timestamp class to target.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write repairs. Default mode is dry-run preview.",
    )
    parser.add_argument(
        "--year-floor",
        type=int,
        default=YEAR_FLOOR,
        help="Minimum valid year for last_conducted.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="How many sample rows to print.",
    )
    parser.add_argument(
        "--backup-dir",
        default="data/maintenance",
        help="Backup directory used when --apply is set.",
    )
    return parser.parse_args()


def _resolve_database_url() -> str:
    for key, value in load_local_env().items():
        os.environ.setdefault(key, value)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return database_url


def main() -> None:
    args = _parse_args()
    result = asyncio.run(
        run_repair(
            database_url=_resolve_database_url(),
            brain_id=args.brain_id,
            policy=args.policy,
            apply=args.apply,
            backup_dir=Path(args.backup_dir),
            year_floor=args.year_floor,
            sample_limit=args.sample_limit,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
