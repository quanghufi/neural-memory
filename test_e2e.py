"""Test SupaBrain E2E: Brain create -> encode memory -> recall."""
import asyncio
import asyncpg
from neural_memory.storage.postgres import PostgreSQLStorage
from neural_memory.core.brain import Brain
from neural_memory.engine.encoder import MemoryEncoder
from neural_memory.engine.retrieval import ReflexPipeline


async def test():
    store = PostgreSQLStorage(
        host='aws-1-ap-southeast-1.pooler.supabase.com',
        port=5432,
        user='postgres.ndnzdahhvolftrclunlc',
        password='aQ@@020319@@',
        database='postgres'
    )
    await store.initialize()
    
    # Check existing brains
    conn = await asyncpg.connect(
        host='aws-1-ap-southeast-1.pooler.supabase.com',
        port=5432,
        user='postgres.ndnzdahhvolftrclunlc',
        password='aQ@@020319@@',
        database='postgres',
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
