import math
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("supabrain_mcp.py")
STARTUP_MARKER = "\ntry:\n    _main()"


def _load_wrapper_namespace() -> dict[str, object]:
    source = MODULE_PATH.read_text(encoding="utf-8")
    if STARTUP_MARKER not in source:
        raise AssertionError("Could not locate supabrain_mcp startup marker for test harness")

    prefix, _ = source.rsplit(STARTUP_MARKER, 1)
    namespace = {
        "__file__": str(MODULE_PATH),
        "__name__": "supabrain_mcp_under_test",
    }
    exec(compile(prefix, str(MODULE_PATH), "exec"), namespace)
    return namespace


class _FakeFiber:
    def __init__(self, last_conducted: datetime | None, salience: float = 0.5) -> None:
        self.last_conducted = last_conducted
        self.salience = salience


class SupabrainMcpReflexTimePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._module_backup: dict[str, types.ModuleType | None] = {}

    def tearDown(self) -> None:
        for name, module in self._module_backup.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def _install_fake_reflex_module(self):
        module_names = (
            "neural_memory",
            "neural_memory.engine",
            "neural_memory.engine.reflex_activation",
        )
        for name in module_names:
            self._module_backup.setdefault(name, sys.modules.get(name))

        neural_memory_mod = types.ModuleType("neural_memory")
        engine_mod = types.ModuleType("neural_memory.engine")
        reflex_mod = types.ModuleType("neural_memory.engine.reflex_activation")

        class ReflexActivation:
            def _compute_time_factor(self, fiber, reference_time):
                if fiber.last_conducted is None:
                    return 0.3 + 0.4 * fiber.salience

                age_hours = (reference_time - fiber.last_conducted).total_seconds() / 3600
                return max(0.1, 1.0 / (1.0 + math.exp((age_hours - 72) / 36)))

        reflex_mod.ReflexActivation = ReflexActivation
        neural_memory_mod.engine = engine_mod
        engine_mod.reflex_activation = reflex_mod

        sys.modules["neural_memory"] = neural_memory_mod
        sys.modules["neural_memory.engine"] = engine_mod
        sys.modules["neural_memory.engine.reflex_activation"] = reflex_mod

        return ReflexActivation

    def test_old_fibers_are_clamped_instead_of_overflowing(self):
        namespace = _load_wrapper_namespace()
        self.assertIn("_patch_reflex_time_factor_overflow", namespace)

        reflex_activation_cls = self._install_fake_reflex_module()
        namespace["_patch_reflex_time_factor_overflow"]()

        activation = reflex_activation_cls()
        ancient_fiber = _FakeFiber(
            last_conducted=datetime.now(UTC) - timedelta(days=365 * 4),
            salience=0.8,
        )

        time_factor = activation._compute_time_factor(ancient_fiber, datetime.now(UTC))

        self.assertEqual(time_factor, 0.1)


if __name__ == "__main__":
    unittest.main()
