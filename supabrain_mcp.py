"""
SupaBrain MCP Server — Neural Memory on Supabase.
Wrapper that registers PostgreSQLStorage plugin, then starts nmem-mcp.
"""
import os
import re
import sys
import logging
import traceback
from pathlib import Path
from urllib.parse import unquote, urlparse

# Silence all logging to stderr (MCP uses stdio, stderr output can cause EOF)
logging.disable(logging.CRITICAL)


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


def _replace_or_append(content: str, pattern: str, replacement: str) -> str:
    if re.search(pattern, content, flags=re.MULTILINE):
        return re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)
    suffix = "" if not content or content.endswith("\n") else "\n"
    return f"{content}{suffix}{replacement}\n"


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


_load_local_env()
os.environ.setdefault("NM_MODE", "postgres")
_configure_postgres_backend()

# Add project dir for supabrain_plugin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Register plugin (silenced)
try:
    import supabrain_plugin
except Exception:
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabrain_mcp_error.log")
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("Failed to import supabrain_plugin\n")
        fh.write(traceback.format_exc())
        fh.write("\n")
    raise SystemExit(1)

# Start MCP server
from neural_memory.mcp.server import main
main()
