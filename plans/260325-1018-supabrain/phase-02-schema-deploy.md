# Phase 02: Database Schema Deploy
Status: ⬜ Pending
Dependencies: Phase 01

## Objective
Deploy neural-memory PostgreSQL schema lên Supabase, bao gồm 10 tables + indexes.

## Schema Reference
File tham khảo: `docs/pg_schema_ref.py` (copy từ neural-memory source)

## Tables (10 total)

| # | Table | Mô tả | Key Columns |
|---|-------|--------|-------------|
| 1 | `brains` | Container + config | id, name, config (JSONB), owner_id |
| 2 | `neurons` | Đơn vị thông tin | id, brain_id, type, content, embedding (vector), content_tsv |
| 3 | `neuron_states` | Activation tracking | neuron_id, brain_id, activation_level, decay_rate |
| 4 | `synapses` | Connections (24 types) | id, brain_id, source_id, target_id, type, weight |
| 5 | `fibers` | Memory pathways | id, brain_id, neuron_ids (JSONB), conductivity |
| 6 | `fiber_neurons` | Junction M:N | brain_id, fiber_id, neuron_id |
| 7 | `typed_memories` | 14 memory types | fiber_id, brain_id, memory_type, priority, trust_score |
| 8 | `projects` | Project grouping | id, brain_id, name |
| 9 | `cognitive_state` | Hypothesis tracking | neuron_id, brain_id, confidence, status |
| 10 | `hot_index` | Ranked cognitive summary | brain_id, slot, category |
| 11 | `knowledge_gaps` | Metacognition | id, brain_id, topic, priority |

## Implementation Steps
1. [ ] Mở Supabase SQL Editor
2. [ ] Chạy CREATE EXTENSION vector
3. [ ] Chạy CREATE TABLE cho từng table (theo thứ tự dependency):
   - brains → neurons → neuron_states → synapses → fibers → fiber_neurons → typed_memories → projects → cognitive_state → hot_index → knowledge_gaps
4. [ ] Chạy CREATE INDEX cho performance
5. [ ] Verify tables trong Supabase Table Editor
6. [ ] Test cơ bản: INSERT/SELECT neuron

## SQL Script
Sử dụng schema từ `docs/pg_schema_ref.py`, chuyển sang SQL thuần:
```sql
-- Step 1: Extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2-11: Tables (xem pg_schema_ref.py)
-- Neural-memory đã có sẵn SQL chuẩn PostgreSQL
-- Chỉ cần chạy từng statement trong _INIT_SQL_TEMPLATE
```

## Supabase-Specific Adjustments
- [ ] Embedding dimension: 384 (default) — Supabase pgvector hỗ trợ tốt
- [ ] tsvector: Supabase PostgreSQL hỗ trợ native
- [ ] JSONB: Supabase PostgreSQL hỗ trợ native
- [ ] TIMESTAMPTZ: Supabase PostgreSQL hỗ trợ native

## Test Criteria
- [ ] Tất cả 11 tables đã tạo thành công
- [ ] Indexes đã tạo
- [ ] INSERT test neuron thành công
- [ ] SELECT với tsvector search hoạt động
- [ ] pgvector embedding insert/query hoạt động

---
Next Phase: [phase-03-connection-config.md](./phase-03-connection-config.md)
