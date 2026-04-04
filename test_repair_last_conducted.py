import importlib.util
import unittest
from datetime import UTC, datetime
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("scripts") / "repair_last_conducted.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("repair_last_conducted", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load repair_last_conducted module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[tuple[datetime, str]]]] = []

    async def executemany(self, sql: str, args: list[tuple[datetime, str]]) -> None:
        self.executed.append((sql, args))


class RepairLastConductedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.created_at = datetime(2026, 3, 30, 7, 4, 35, tzinfo=UTC)
        self.pre_2026 = {
            "id": "fiber-pre-2026",
            "brain_id": "default",
            "created_at": self.created_at,
            "last_conducted": datetime(2022, 3, 4, 23, 9, 20, tzinfo=UTC),
        }
        self.before_created = {
            "id": "fiber-before-created",
            "brain_id": "default",
            "created_at": self.created_at,
            "last_conducted": datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        }
        self.valid = {
            "id": "fiber-valid",
            "brain_id": "default",
            "created_at": self.created_at,
            "last_conducted": datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        }

    def test_find_candidates_filters_invalid_rows(self):
        module = _load_module()

        candidates = module.find_candidates(
            [self.pre_2026, self.before_created, self.valid],
            policy="all",
        )

        self.assertEqual([candidate["id"] for candidate in candidates], ["fiber-pre-2026", "fiber-before-created"])

    def test_normalize_last_conducted_uses_created_at(self):
        module = _load_module()

        normalized = module.normalize_last_conducted(
            created_at=self.created_at,
            last_conducted=self.pre_2026["last_conducted"],
        )

        self.assertEqual(normalized, self.created_at)

    def test_normalize_last_conducted_keeps_valid_timestamp(self):
        module = _load_module()

        normalized = module.normalize_last_conducted(
            created_at=self.created_at,
            last_conducted=self.valid["last_conducted"],
        )

        self.assertEqual(normalized, self.valid["last_conducted"])

    async def test_repair_candidates_dry_run_skips_updates(self):
        module = _load_module()
        conn = _FakeConnection()

        result = await module.repair_candidates(
            conn=conn,
            candidates=module.find_candidates([self.pre_2026], policy="all"),
            apply=False,
        )

        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(conn.executed, [])


if __name__ == "__main__":
    unittest.main()
