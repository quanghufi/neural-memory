# Phase 01: Supabase Project Setup
Status: ⬜ Pending
Dependencies: None

## Objective
Tạo Supabase project free tier, bật pgvector extension, lấy connection credentials.

## Implementation Steps
1. [ ] Đăng nhập Supabase Dashboard (https://supabase.com)
2. [ ] Tạo project mới (region: Singapore cho latency tốt nhất)
3. [ ] Bật extension `vector` (pgvector) trong SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. [ ] Lấy connection credentials:
   - `Host`: db.[project-ref].supabase.co
   - `Port`: 5432 (hoặc 6543 cho connection pooler)
   - `Database`: postgres
   - `User`: postgres
   - `Password`: [project password]
5. [ ] Lưu credentials vào `.env` file:
   ```env
   SUPABASE_URL=https://[ref].supabase.co
   SUPABASE_ANON_KEY=eyJ...
   SUPABASE_DB_HOST=db.[ref].supabase.co
   SUPABASE_DB_PORT=5432
   SUPABASE_DB_NAME=postgres
   SUPABASE_DB_USER=postgres
   SUPABASE_DB_PASS=[password]
   DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
   ```
6. [ ] Test connection:
   ```bash
   psql "postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres"
   ```

## Test Criteria
- [ ] Có thể connect tới Supabase PostgreSQL từ local
- [ ] pgvector extension đã bật
- [ ] `.env` file có đủ credentials

## Notes
- Supabase free tier: 500MB DB, 2 projects, auto-pause sau 7 ngày
- Dùng connection pooler port 6543 nếu có nhiều concurrent connections
- **QUAN TRỌNG:** Không commit `.env` vào git!

---
Next Phase: [phase-02-schema-deploy.md](./phase-02-schema-deploy.md)
