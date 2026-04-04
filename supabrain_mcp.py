"""
Neural Memory MCP Server — Self-hosted PostgreSQL on VPS.
Configures built-in postgres backend, then starts nmem-mcp.
"""
import os
import re
import logging
import traceback
from pathlib import Path
from urllib.parse import unquote, urlparse

# Silence stderr logging (MCP uses stdio, stderr output can cause EOF)
# But redirect to a debug log file so we can diagnose tool failures
_debug_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabrain_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    filename=_debug_log_path,
    filemode="a",
)
# Prevent any output to stderr (MCP needs clean stdio)
logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler) or h.stream != __import__('sys').stderr]
_file_handler = logging.FileHandler(_debug_log_path, mode="a", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_file_handler)
logging.getLogger().setLevel(logging.DEBUG)


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _load_local_env() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _upsert_top_level_scalar(content: str, key: str, value_literal: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}\s*=.*\n?"
    content = re.sub(pattern, "", content)

    section_match = re.search(r"(?m)^\[", content)
    insert_at = section_match.start() if section_match else len(content)

    prefix = content[:insert_at]
    suffix = content[insert_at:]
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    prefix += f"{key} = {value_literal}\n"
    return prefix + suffix


def _upsert_section(content: str, section_name: str, section_body: str) -> str:
    pattern = rf"(?ms)^\[{re.escape(section_name)}\]\n(?:.*\n)*?(?=^\[|\Z)"
    block = f"[{section_name}]\n{section_body}"
    if re.search(pattern, content):
        return re.sub(pattern, block, content, count=1)
    suffix = "" if not content or content.endswith("\n") else "\n"
    return f"{content}{suffix}{block}"


def _configure_postgres_backend() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set; create .env or export it in the MCP environment")

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must start with postgres:// or postgresql://")

    data_dir = Path(os.environ.get("NEURALMEMORY_DIR", str(Path.home() / ".neuralmemory")))
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "brains").mkdir(parents=True, exist_ok=True)

    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = unquote(parsed.path.lstrip("/") or "postgres")
    user = unquote(parsed.username or "postgres")
    password = unquote(parsed.password or "")
    current_brain = os.environ.get("NEURALMEMORY_BRAIN") or os.environ.get("NMEM_BRAIN") or "default"

    config_path = data_dir / "config.toml"
    content = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    content = _upsert_top_level_scalar(
        content,
        "current_brain",
        f'"{_toml_escape(current_brain)}"',
    )
    content = _upsert_top_level_scalar(content, "storage_backend", '"postgres"')
    content = _upsert_section(
        content,
        "postgres",
        (
            f'host = "{_toml_escape(host)}"\n'
            f"port = {port}\n"
            f'database = "{_toml_escape(database)}"\n'
            f'user = "{_toml_escape(user)}"\n'
            'password = ""\n'
        ),
    )
    config_path.write_text(content, encoding="utf-8")

    os.environ["NEURAL_MEMORY_POSTGRES_HOST"] = host
    os.environ["NEURAL_MEMORY_POSTGRES_PORT"] = str(port)
    os.environ["NEURAL_MEMORY_POSTGRES_DATABASE"] = database
    os.environ["NEURAL_MEMORY_POSTGRES_USER"] = user
    os.environ["NEURAL_MEMORY_POSTGRES_PASSWORD"] = password
    os.environ["NEURALMEMORY_DIR"] = str(data_dir)


def _read_positive_timeout(env_name: str, default: float) -> float:
    raw_value = os.environ.get(env_name, "").strip()
    if not raw_value:
        return default
    try:
        parsed_value = float(raw_value)
    except ValueError:
        return default
    return parsed_value if parsed_value > 0 else default


def _patch_heavy_save_timeouts() -> None:
    """
    Increase the default 30s budget for save-heavy MCP operations.

    neural_memory currently enforces a 30s MCP tool timeout and also uses 30s
    as the default asyncpg per-query timeout in PostgresBaseMixin. That is too
    small for large remember/train batches on remote Postgres.

    We patch the wrapper, not site-packages, so upgrades remain safe.
    """
    import importlib

    save_tool_timeout = _read_positive_timeout("NMEM_SAVE_TOOL_TIMEOUT_SECONDS", 300.0)
    save_query_timeout = _read_positive_timeout(
        "NMEM_SAVE_QUERY_TIMEOUT_SECONDS",
        save_tool_timeout,
    )
    heavy_save_tools = frozenset(
        {
            # ── Core memory operations ──
            "nmem_remember",
            "nmem_remember_batch",
            "nmem_auto",
            "nmem_recall",
            "nmem_context",
            "nmem_show",
            "nmem_edit",
            "nmem_forget",
            "nmem_pin",
            "nmem_todo",
            "nmem_refine",
            "nmem_report_outcome",
            # ── Project / session persistence ──
            "nmem_eternal",
            "nmem_session",
            "nmem_recap",
            # ── Training & indexing ──
            "nmem_train",
            "nmem_db_train",
            "nmem_index",
            "nmem_watch",
            # ── Code intelligence ──
            "nmem_codeintel_index",
            "nmem_codeintel_search",
            "nmem_codeintel_callers",
            "nmem_codeintel_callees",
            "nmem_codeintel_impact",
            # ── Consolidation & lifecycle ──
            "nmem_consolidate",
            "nmem_lifecycle",
            "nmem_review",
            "nmem_surface",
            "nmem_version",
            # ── Knowledge graph & reasoning ──
            "nmem_hypothesize",
            "nmem_evidence",
            "nmem_predict",
            "nmem_verify",
            "nmem_schema",
            "nmem_explain",
            "nmem_narrative",
            "nmem_cognitive",
            "nmem_gaps",
            # ── Diagnostics & maintenance ──
            "nmem_health",
            "nmem_stats",
            "nmem_evolution",
            "nmem_alerts",
            "nmem_conflicts",
            "nmem_drift",
            "nmem_habits",
            "nmem_suggest",
            "nmem_tool_stats",
            "nmem_budget",
            "nmem_visualize",
            # ── Sync & provenance ──
            "nmem_sync",
            "nmem_sync_config",
            "nmem_sync_status",
            "nmem_source",
            "nmem_provenance",
        }
    )

    def _should_extend_tool_timeout(tool_name: str) -> bool:
        if tool_name in heavy_save_tools:
            return True
        return tool_name.startswith("nmem_train")

    def _lift_default_timeout(timeout: float | None) -> float:
        if timeout is None:
            return save_query_timeout
        try:
            timeout_value = float(timeout)
        except (TypeError, ValueError):
            return save_query_timeout
        if timeout_value == 30.0:
            return save_query_timeout
        return timeout_value

    try:
        server_module = importlib.import_module("neural_memory.mcp.server")
        original_handle_message = server_module.handle_message

        if not getattr(original_handle_message, "_supabrain_heavy_save_timeout_patch", False):

            async def _handle_message(server, message, _orig=original_handle_message):
                if message.get("method") != "tools/call":
                    return await _orig(server, message)

                params = message.get("params", {})
                tool_name = str(params.get("name", ""))
                if not _should_extend_tool_timeout(tool_name):
                    return await _orig(server, message)

                previous_timeout = getattr(server_module, "_TOOL_CALL_TIMEOUT", 30.0)
                server_module._TOOL_CALL_TIMEOUT = max(float(previous_timeout), save_tool_timeout)
                try:
                    return await _orig(server, message)
                finally:
                    server_module._TOOL_CALL_TIMEOUT = previous_timeout

            _handle_message._supabrain_heavy_save_timeout_patch = True
            server_module.handle_message = _handle_message
    except Exception:
        pass

    try:
        postgres_base_module = importlib.import_module(
            "neural_memory.storage.postgres.postgres_base"
        )
        postgres_base_cls = postgres_base_module.PostgresBaseMixin

        def _wrap_default_timeout(method_name: str) -> None:
            original_method = getattr(postgres_base_cls, method_name, None)
            if original_method is None or getattr(
                original_method,
                "_supabrain_heavy_save_timeout_patch",
                False,
            ):
                return

            async def _wrapped(self, *args, timeout: float = 30.0, _orig=original_method, **kwargs):
                effective_timeout = _lift_default_timeout(timeout)
                return await _orig(self, *args, timeout=effective_timeout, **kwargs)

            _wrapped._supabrain_heavy_save_timeout_patch = True
            setattr(postgres_base_cls, method_name, _wrapped)

        for method_name in ("_query", "_query_ro", "_query_one", "_executemany"):
            _wrap_default_timeout(method_name)
    except Exception:
        pass


def _patch_reflex_time_factor_overflow() -> None:
    """
    Clamp reflex time-factor exponent so ancient fibers cannot overflow math.exp().

    neural_memory's ReflexActivation uses a sigmoid over fiber age in hours.
    Brains migrated from older datasets can contain fibers last_conducted years
    in the past, which pushes the exponent far above Python's safe exp() range.
    """
    import importlib
    import math

    try:
        reflex_module = importlib.import_module("neural_memory.engine.reflex_activation")
        reflex_cls = reflex_module.ReflexActivation
        original_method = getattr(reflex_cls, "_compute_time_factor", None)

        if original_method is None or getattr(
            original_method,
            "_supabrain_time_factor_clamp_patch",
            False,
        ):
            return

        def _safe_compute_time_factor(self, fiber, reference_time):
            if fiber.last_conducted is None:
                # Preserve upstream fallback for never-conducted fibers.
                return 0.3 + 0.4 * fiber.salience

            age_hours = (reference_time - fiber.last_conducted).total_seconds() / 3600
            exponent = (age_hours - 72) / 36
            exponent = max(-100.0, min(100.0, exponent))
            return max(0.1, 1.0 / (1.0 + math.exp(exponent)))

        _safe_compute_time_factor._supabrain_time_factor_clamp_patch = True
        reflex_cls._compute_time_factor = _safe_compute_time_factor
    except Exception:
        pass


def _patch_path_validation() -> None:
    """
    Monkey-patch nmem handlers to allow scanning codebases outside CWD.

    By default nmem_index/nmem_train reject paths not under the MCP server's
    working directory.  This patch temporarily chdir() to the target path so
    the original is_relative_to(cwd) check passes.

    Lives in wrapper (not site-packages) → survives pip upgrades.
    """
    import importlib

    _BLOCKED = tuple(
        Path(p).resolve()
        for p in [
            os.environ.get("SYSTEMROOT", r"C:\Windows"),
            r"C:\Program Files",
            r"C:\Program Files (x86)",
        ]
        if Path(p).exists()
    )

    def _safe(p: Path) -> bool:
        r = p.resolve()
        return not any(r.is_relative_to(b) for b in _BLOCKED)

    # ── index_handler._index_scan ──
    try:
        idx = importlib.import_module("neural_memory.mcp.index_handler")
        _orig_idx = idx.IndexHandler._index_scan

        async def _idx(self, args, storage):
            p = Path(args.get("path", ".")).resolve()
            if not p.is_dir():
                return {"error": "Not a directory"}
            if not _safe(p):
                return {"error": "Path is in a blocked system directory"}
            saved = Path.cwd()
            try:
                os.chdir(p)
                return await _orig_idx(self, args, storage)
            finally:
                os.chdir(saved)

        idx.IndexHandler._index_scan = _idx
    except Exception:
        pass

    # ── train_handler._train_docs ──
    try:
        trn = importlib.import_module("neural_memory.mcp.train_handler")
        _orig_trn = trn.TrainHandler._train_docs

        async def _trn(self, args):
            p = Path(args.get("path", ".")).resolve()
            if not p.exists():
                return {"error": "Path not found"}
            if not _safe(p):
                return {"error": "Path is in a blocked system directory"}
            saved = Path.cwd()
            try:
                os.chdir(p if p.is_dir() else p.parent)
                return await _orig_trn(self, args)
            finally:
                os.chdir(saved)

        trn.TrainHandler._train_docs = _trn
    except Exception:
        pass

    # ── watch_handler (if present) ──
    try:
        w = importlib.import_module("neural_memory.mcp.watch_handler")
        if hasattr(w, "WatchHandler") and hasattr(w.WatchHandler, "_watch_scan"):
            _orig_w = w.WatchHandler._watch_scan

            async def _ws(self, args, storage):
                p = Path(args.get("directory", ".")).resolve()
                if not _safe(p):
                    return {"error": "Path is in a blocked system directory"}
                saved = Path.cwd()
                try:
                    os.chdir(p if p.is_dir() else p.parent)
                    return await _orig_w(self, args, storage)
                finally:
                    os.chdir(saved)

            w.WatchHandler._watch_scan = _ws
    except Exception:
        pass


def _main():
    _load_local_env()
    os.environ.setdefault("NM_MODE", "postgres")
    _configure_postgres_backend()
    _patch_heavy_save_timeouts()
    _patch_reflex_time_factor_overflow()
    _patch_path_validation()

    # CodeIntel: register plugin BEFORE main() starts MCP server
    try:
        from codeintel.tools import CodeIntelPlugin
        from neural_memory.plugins import register
        register(CodeIntelPlugin())
    except Exception as e:
        # Don't fail if plugins can't load, just log
        pass

    from neural_memory.mcp.server import main
    main()


try:
    _main()
except Exception:
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabrain_mcp_error.log")
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("Startup failed\n")
        fh.write(traceback.format_exc())
        fh.write("\n")
    raise SystemExit(1)
