import os
import sys
import types
import unittest
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


class SupabrainMcpTimeoutPatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._module_backup: dict[str, types.ModuleType | None] = {}
        self._env_backup = {
            "NMEM_SAVE_TOOL_TIMEOUT_SECONDS": os.environ.get("NMEM_SAVE_TOOL_TIMEOUT_SECONDS"),
            "NMEM_SAVE_QUERY_TIMEOUT_SECONDS": os.environ.get("NMEM_SAVE_QUERY_TIMEOUT_SECONDS"),
        }
        for key in self._env_backup:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for name, module in self._module_backup.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _install_fake_neural_memory_modules(self):
        module_names = (
            "neural_memory",
            "neural_memory.mcp",
            "neural_memory.mcp.server",
            "neural_memory.storage",
            "neural_memory.storage.postgres",
            "neural_memory.storage.postgres.postgres_base",
        )
        for name in module_names:
            self._module_backup.setdefault(name, sys.modules.get(name))

        neural_memory_mod = types.ModuleType("neural_memory")
        mcp_mod = types.ModuleType("neural_memory.mcp")
        server_mod = types.ModuleType("neural_memory.mcp.server")
        storage_mod = types.ModuleType("neural_memory.storage")
        postgres_mod = types.ModuleType("neural_memory.storage.postgres")
        postgres_base_mod = types.ModuleType("neural_memory.storage.postgres.postgres_base")

        server_mod._TOOL_CALL_TIMEOUT = 30.0

        async def handle_message(_server, message):
            return {
                "tool": message.get("params", {}).get("name"),
                "timeout": server_mod._TOOL_CALL_TIMEOUT,
            }

        server_mod.handle_message = handle_message

        class PostgresBaseMixin:
            async def _query(self, sql: str, *args, timeout: float = 30.0):
                return timeout

            async def _query_ro(self, sql: str, *args, timeout: float = 30.0):
                return timeout

            async def _query_one(self, sql: str, *args, timeout: float = 30.0):
                return timeout

            async def _executemany(self, sql: str, args_list, timeout: float = 30.0):
                return timeout

        postgres_base_mod.PostgresBaseMixin = PostgresBaseMixin

        neural_memory_mod.mcp = mcp_mod
        neural_memory_mod.storage = storage_mod
        mcp_mod.server = server_mod
        storage_mod.postgres = postgres_mod
        postgres_mod.postgres_base = postgres_base_mod

        sys.modules["neural_memory"] = neural_memory_mod
        sys.modules["neural_memory.mcp"] = mcp_mod
        sys.modules["neural_memory.mcp.server"] = server_mod
        sys.modules["neural_memory.storage"] = storage_mod
        sys.modules["neural_memory.storage.postgres"] = postgres_mod
        sys.modules["neural_memory.storage.postgres.postgres_base"] = postgres_base_mod

        return server_mod, PostgresBaseMixin

    async def test_save_tools_get_a_longer_tool_timeout(self):
        namespace = _load_wrapper_namespace()
        server_mod, _ = self._install_fake_neural_memory_modules()

        namespace["_patch_heavy_save_timeouts"]()

        remember_response = await server_mod.handle_message(
            object(),
            {"method": "tools/call", "params": {"name": "nmem_remember"}},
        )
        recall_response = await server_mod.handle_message(
            object(),
            {"method": "tools/call", "params": {"name": "nmem_recall"}},
        )

        self.assertEqual(remember_response["timeout"], 300.0)
        self.assertEqual(recall_response["timeout"], 30.0)

    async def test_default_postgres_query_timeouts_are_elevated(self):
        namespace = _load_wrapper_namespace()
        _, postgres_base_cls = self._install_fake_neural_memory_modules()

        namespace["_patch_heavy_save_timeouts"]()

        storage = postgres_base_cls()
        self.assertEqual(await storage._query("select 1"), 300.0)
        self.assertEqual(await storage._query_ro("select 1"), 300.0)
        self.assertEqual(await storage._query_one("select 1"), 300.0)
        self.assertEqual(await storage._executemany("select 1", []), 300.0)

        self.assertEqual(await storage._query("select 1", timeout=5.0), 5.0)
        self.assertEqual(await storage._query_one("select 1", timeout=120.0), 120.0)

    async def test_env_overrides_apply_to_tool_and_query_timeouts(self):
        os.environ["NMEM_SAVE_TOOL_TIMEOUT_SECONDS"] = "600"
        os.environ["NMEM_SAVE_QUERY_TIMEOUT_SECONDS"] = "480"

        namespace = _load_wrapper_namespace()
        server_mod, postgres_base_cls = self._install_fake_neural_memory_modules()

        namespace["_patch_heavy_save_timeouts"]()

        remember_response = await server_mod.handle_message(
            object(),
            {"method": "tools/call", "params": {"name": "nmem_remember_batch"}},
        )

        storage = postgres_base_cls()

        self.assertEqual(remember_response["timeout"], 600.0)
        self.assertEqual(await storage._query("select 1"), 480.0)
        self.assertEqual(await storage._executemany("select 1", []), 480.0)


if __name__ == "__main__":
    unittest.main()
