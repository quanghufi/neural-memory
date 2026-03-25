# Phase 03: Connection Config
Status: ⬜ Pending
Dependencies: Phase 01, Phase 02

## Objective
Cấu hình neural-memory để sử dụng PostgreSQLStorage trỏ về Supabase.

## How Neural Memory PostgreSQL Works
Neural-memory đã có sẵn `PostgreSQLStorage` class:
- Location: `neural_memory/storage/postgres/postgres_store.py` (111 lines)
- Uses: `asyncpg.create_pool()` with host/port/user/password/database
- Factory: `BrainModeConfig` selects storage backend
- Schema: `postgres_schema.py` → `ensure_schema()` auto-creates tables

## Implementation Steps

### Option A: Dùng neural-memory CLI config
1. [ ] Cài neural-memory với PostgreSQL support:
   ```bash
   pip install "neural-memory[server]"
   # hoặc nếu cần embeddings:
   pip install "neural-memory[all]"
   ```
2. [ ] Cấu hình brain mode = POSTGRES:
   ```bash
   nmem config set mode postgres
   nmem config set postgres_host db.[ref].supabase.co
   nmem config set postgres_port 5432
   nmem config set postgres_user postgres
   nmem config set postgres_pass [password]
   nmem config set postgres_db postgres
   ```
3. [ ] Hoặc dùng environment variable:
   ```bash
   export NM_MODE=postgres
   export NM_POSTGRES_HOST=db.[ref].supabase.co
   export NM_POSTGRES_PORT=5432
   export NM_POSTGRES_USER=postgres
   export NM_POSTGRES_PASS=[password]
   export NM_POSTGRES_DB=postgres
   ```

### Option B: Dùng DATABASE_URL (đơn giản hơn)
1. [ ] Set DATABASE_URL:
   ```bash
   export DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
   export NM_MODE=postgres
   ```

### Option C: Config file (~/.neural-memory/config.json)
1. [ ] Tạo/sửa config file:
   ```json
   {
     "mode": "postgres",
     "postgres": {
       "host": "db.[ref].supabase.co",
       "port": 5432,
       "user": "postgres",
       "password": "[password]",
       "database": "postgres"
     }
   }
   ```

## SSL/TLS for Supabase
- [ ] Supabase yêu cầu SSL — cần thêm `sslmode=require`:
   ```
   DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres?sslmode=require
   ```
- [ ] Hoặc set `NM_POSTGRES_SSL=require`

## MCP Server Config
- [ ] Cập nhật MCP server config để truyền env vars:
  ```json
  {
    "neural-memory": {
      "command": "uvx",
      "args": ["neural-memory"],
      "env": {
        "NM_MODE": "postgres",
        "DATABASE_URL": "postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres?sslmode=require"
      }
    }
  }
  ```

## Test Criteria
- [ ] `nmem brain list` — kết nối thành công, trả về danh sách brains
- [ ] `nmem brain create supabrain` — tạo brain mới trên Supabase
- [ ] `nmem remember "test memory"` — lưu memory thành công
- [ ] `nmem recall "test"` — recall memory thành công
- [ ] Check Supabase Table Editor — data xuất hiện trong tables

## Troubleshooting
- **Connection refused:** Check Supabase project không bị paused
- **SSL error:** Thêm `?sslmode=require` vào DATABASE_URL
- **asyncpg not installed:** `pip install asyncpg`
- **pgvector error:** Đảm bảo đã chạy `CREATE EXTENSION vector` ở Phase 02

---
Next Phase: [phase-04-rls-auth.md](./phase-04-rls-auth.md)
