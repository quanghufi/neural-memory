"""
Fast migration v3: SQLite brain -> Supabase PostgreSQL.
Per-row error recovery + auto type coercion.
"""
import asyncio
import sqlite3
import asyncpg
from pathlib import Path

DB_PATH = str(Path.home() / ".neuralmemory" / "brains" / "default.db")
PG_DSN = (
    "postgresql://postgres.ndnzdahhvolftrclunlc:"
    "aQ%40%40020319%40%40@"
    "aws-1-ap-southeast-1.pooler.supabase.com:5432/"
    "postgres"
)

TABLES = [
    "brains", "neurons", "synapses", "fibers",
    "fiber_neurons", "typed_memories", "knowledge_gaps",
    "drift_clusters", "spaced_repetition", "change_log",
    "review_sessions",
]

async def get_pg_schema(conn, table):
    rows = await conn.fetch(
        "SELECT column_name, data_type, udt_name "
        "FROM information_schema.columns WHERE table_name=$1 "
        "ORDER BY ordinal_position", table)
    return {r['column_name']: r['data_type'] for r in rows}

def coerce(val, pg_type):
    if val is None:
        return None
    if pg_type == 'boolean':
        if isinstance(val, int):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)
    if pg_type in ('integer', 'bigint', 'smallint'):
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
    if pg_type in ('double precision', 'real', 'numeric'):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    if 'timestamp' in pg_type:
        from datetime import datetime
        if isinstance(val, str):
            # Parse ISO format timestamps from SQLite
            try:
                # Handle various ISO formats
                val = val.replace('Z', '+00:00').replace('T', ' ')
                if '.' in val and '+' in val:
                    # "2025-01-15 10:30:00.123456+00:00"
                    return datetime.fromisoformat(val)
                elif '.' in val:
                    return datetime.fromisoformat(val)
                elif '+' in val or val.endswith('00:00'):
                    return datetime.fromisoformat(val)
                else:
                    return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None
        if isinstance(val, (int, float)):
            from datetime import datetime
            try:
                return datetime.fromtimestamp(val)
            except:
                return None
        return None
    if pg_type == 'ARRAY' or pg_type == 'USER-DEFINED':
        return None
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except:
            return val.hex()
    return val

async def migrate():
    print(f"=== Neural Memory Migration ===")
    print(f"Local: {DB_PATH}")
    
    local = sqlite3.connect(DB_PATH)
    local.row_factory = sqlite3.Row
    
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=3, ssl='require')
    
    async with pool.acquire() as conn:
        existing = {r['tablename'] for r in await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        
        # Disable FK constraints
        await conn.execute("SET session_replication_role = 'replica'")
        
        total_migrated = 0
        total_errors = 0
        
        for table in TABLES:
            if table not in existing:
                continue
            
            try:
                local_rows = local.execute(f"SELECT * FROM {table}").fetchall()
            except:
                continue
            
            if not local_rows:
                print(f"  {table}: 0 rows")
                continue
            
            local_cols = [d[0] for d in local.execute(f"SELECT * FROM {table} LIMIT 1").description]
            pg_types = await get_pg_schema(conn, table)
            
            # Filter to common columns, skip array/vector columns
            common = []
            for c in local_cols:
                if c in pg_types:
                    pt = pg_types[c]
                    if pt not in ('ARRAY', 'USER-DEFINED'):
                        common.append(c)
            
            if not common:
                print(f"  {table}: no compatible columns")
                continue
            
            col_idx = [local_cols.index(c) for c in common]
            col_list = ", ".join(f'"{c}"' for c in common)
            ph = ", ".join(f"${i+1}" for i in range(len(common)))
            sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({ph}) ON CONFLICT DO NOTHING'
            
            # Clear first
            await conn.execute(f'DELETE FROM "{table}"')
            
            ok = 0
            err = 0
            total = len(local_rows)
            
            # Insert one-by-one for error recovery (still fast for < 30K rows)
            for row in local_rows:
                vals = tuple(coerce(row[i], pg_types[common[j]]) for j, i in enumerate(col_idx))
                try:
                    await conn.execute(sql, *vals)
                    ok += 1
                except Exception as e:
                    err += 1
                    if err <= 3:
                        print(f"\n  ERR {table}: {str(e)[:120]}")
                
                if (ok + err) % 500 == 0:
                    print(f"  {table}: {ok+err}/{total}...", end="\r")
            
            total_migrated += ok
            total_errors += err
            err_s = f" ({err} skip)" if err else ""
            print(f"  {table}: {ok}/{total}{err_s}                    ")
        
        await conn.execute("SET session_replication_role = 'origin'")
    
    # Verify
    async with pool.acquire() as conn:
        print(f"\n=== Verify ===")
        for table in TABLES:
            if table not in existing:
                continue
            pg_n = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')
            try:
                lc_n = local.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except:
                lc_n = 0
            s = "OK" if pg_n >= lc_n else "DIFF"
            print(f"  [{s}] {table}: PG={pg_n} Local={lc_n}")
    
    local.close()
    await pool.close()
    print(f"\nTotal: {total_migrated} migrated, {total_errors} errors")

asyncio.run(migrate())
