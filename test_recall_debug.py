"""Quick debug script to reproduce nmem_recall exact mode failure."""
import asyncio
import os
import sys
import traceback
import logging

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Load .env
from pathlib import Path
env_path = Path("d:/neural-memory/.env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# Configure postgres backend like supabrain_mcp.py does
from urllib.parse import unquote, urlparse

database_url = os.environ.get("DATABASE_URL", "")
parsed = urlparse(database_url)
host = parsed.hostname or "localhost"
port = parsed.port or 5432
database = unquote(parsed.path.lstrip("/") or "postgres")
user = unquote(parsed.username or "postgres")
password = unquote(parsed.password or "")

os.environ["NEURAL_MEMORY_POSTGRES_HOST"] = host
os.environ["NEURAL_MEMORY_POSTGRES_PORT"] = str(port)
os.environ["NEURAL_MEMORY_POSTGRES_DATABASE"] = database
os.environ["NEURAL_MEMORY_POSTGRES_USER"] = user
os.environ["NEURAL_MEMORY_POSTGRES_PASSWORD"] = password

data_dir = Path(os.environ.get("NEURALMEMORY_DIR", str(Path.home() / ".neuralmemory")))
os.environ["NEURALMEMORY_DIR"] = str(data_dir)

# Write config.toml like supabrain_mcp.py does
import re

def _toml_escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')

def _upsert_top_level_scalar(content, key, value_literal):
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

def _upsert_section(content, section_name, section_body):
    pattern = rf"(?ms)^\[{re.escape(section_name)}\]\n(?:.*\n)*?(?=^\[|\Z)"
    block = f"[{section_name}]\n{section_body}"
    if re.search(pattern, content):
        return re.sub(pattern, block, content, count=1)
    suffix = "" if not content or content.endswith("\n") else "\n"
    return f"{content}{suffix}{block}"

config_path = data_dir / "config.toml"
content = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
content = _upsert_top_level_scalar(content, "current_brain", '"default"')
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

async def test():
    try:
        from neural_memory.unified_config import get_config, get_shared_storage
        config = get_config()
        print(f"Config loaded: backend={config.storage_backend}")
        print(f"Current brain: {config.current_brain}")
        
        storage = await get_shared_storage()
        print(f"Storage created: {type(storage).__name__}")
        
        from neural_memory.utils.timeutils import utcnow
        # Get brain
        from neural_memory.mcp.tool_handler_utils import _require_brain_id
        brain_id = _require_brain_id(storage)
        print(f"Brain ID: {brain_id}")
        
        brain = await storage.get_brain(brain_id)
        if not brain:
            print("ERROR: No brain found!")
            return
        print(f"Brain: {brain.name}")
        
        # Let's inspect fibers before querying
        print("\n--- Inspecting Fibers in Database ---")
        fibers = await storage.get_fibers(limit=100)
        print(f"Total fibers listed: {len(fibers)}")
        for f in fibers:
            fid = f.id
            ref_time = utcnow()
            lc = f.last_conducted
            if lc:
                age_hours = (ref_time - lc).total_seconds() / 3600
                z = (age_hours - 72) / 36
                print(f"Fiber {fid}: last_conducted={lc}, age_hours={age_hours:.1f}, z={z:.1f}")
            else:
                print(f"Fiber {fid}: last_conducted=None")

        # Run the ReflexPipeline query (same as _recall does)
        from neural_memory.engine.retrieval import ReflexPipeline, DepthLevel
        from neural_memory.utils.timeutils import utcnow
        
        print("\n--- Running ReflexPipeline.query ---")
        pipeline = ReflexPipeline(storage, brain.config)
        try:
            result = await pipeline.query(
                query="LUÔN tìm trong brain trước bằng nmem_recall codebase index",
                depth=DepthLevel(1),
                max_tokens=3000,
                reference_time=utcnow(),
            )
        except OverflowError as e:
            print(f"CAUGHT OverflowError during query: {e}")
            raise
        print(f"Query OK: confidence={result.confidence}")
        print(f"fibers_matched={result.fibers_matched}")
        print(f"neurons_activated={result.neurons_activated}")
        
        # Now test exact mode path (the code that runs when mode=exact)
        if result.fibers_matched:
            print(f"\n--- Testing exact mode for {len(result.fibers_matched)} fibers ---")
            for fid in result.fibers_matched:
                print(f"\nFiber: {fid}")
                fiber = await storage.get_fiber(fid)
                if not fiber:
                    print("  ERROR: fiber not found")
                    continue
                print(f"  anchor_neuron_id: {fiber.anchor_neuron_id}")
                
                anchor = await storage.get_neuron(fiber.anchor_neuron_id)
                if not anchor:
                    print("  ERROR: anchor neuron not found")
                    continue
                print(f"  content: {anchor.content[:100]}...")
                
                tm = await storage.get_typed_memory(fid)
                print(f"  typed_memory: {tm}")
                if tm:
                    print(f"    memory_type: {tm.memory_type}")
                    print(f"    priority: {tm.priority}")
                    print(f"    tags: {tm.tags}")
                
                # Test citation build
                from neural_memory.mcp.tool_handler_utils import _build_citation_audit
                citation = await _build_citation_audit(storage, anchor.id, True)
                print(f"  citation: {citation}")
        else:
            print("\nNo fibers matched - trying a simpler query...")
            result2 = await pipeline.query(
                query="test",
                depth=DepthLevel(0),
                max_tokens=500,
                reference_time=utcnow(),
            )
            print(f"Simple query: confidence={result2.confidence}, fibers={result2.fibers_matched}")
        
        print("\n=== ALL TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== ERROR ===")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {e}")
        traceback.print_exc()

asyncio.run(test())
