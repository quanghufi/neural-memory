"""Test SupaBrain E2E: Brain create -> encode memory -> recall."""
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import asyncpg
from neural_memory.storage.postgres import PostgreSQLStorage
from neural_memory.core.brain import Brain
from neural_memory.engine.encoder import MemoryEncoder
from neural_memory.engine.retrieval import ReflexPipeline


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_database_url() -> str:
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, value = raw.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return database_url


async def test():
    parsed = urlparse(load_database_url())
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = unquote(parsed.username or "postgres")
    password = unquote(parsed.password or "")
    database = unquote(parsed.path.lstrip("/") or "postgres")

    store = PostgreSQLStorage(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    await store.initialize()
    
    # Check existing brains
    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl='require'
    )
    rows = await conn.fetch('SELECT id, name FROM brains')
    print(f'Existing brains: {len(rows)}')
    for r in rows:
        print(f'  {r["id"]} | {r["name"]}')
    
    # Use existing brain or create new one
    if rows:
        brain_id = rows[0]["id"]
        brain = await store.get_brain(brain_id)
        print(f'Using existing brain: {brain_id}')
    else:
        brain = Brain.create('supabrain')
        brain_id = brain.id
        await store.save_brain(brain)
        print(f'Brain created: {brain_id}')
    
    store.set_brain(brain_id)
    
    # Encode memory
    encoder = MemoryEncoder(store, brain.config)
    try:
        fiber_id = await encoder.encode('Test memory: Supabase PostgreSQL is working perfectly with SupaBrain')
        print(f'Memory encoded! fiber_id: {fiber_id}')
    except Exception as e:
        print(f'Encode error: {type(e).__name__}: {e}')
    
    # Check data
    n_count = await conn.fetchval('SELECT COUNT(*) FROM neurons WHERE brain_id = $1', brain_id)
    s_count = await conn.fetchval('SELECT COUNT(*) FROM synapses WHERE brain_id = $1', brain_id)
    f_count = await conn.fetchval('SELECT COUNT(*) FROM fibers WHERE brain_id = $1', brain_id)
    print(f'Data: {n_count} neurons, {s_count} synapses, {f_count} fibers')
    
    # Recall
    if f_count > 0:
        pipeline = ReflexPipeline(store, brain.config)
        result = await pipeline.query('Supabase')
        print(f'Recall: {result.context[:200] if result.context else "No context"}')
    
    await conn.close()
    await store.close()
    print('\nAll tests done!')

asyncio.run(test())
