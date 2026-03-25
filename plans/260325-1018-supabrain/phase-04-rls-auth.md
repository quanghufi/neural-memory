# Phase 04: RLS + Auth Policies
Status: ⬜ Pending
Dependencies: Phase 02

## Objective
Thêm Row Level Security (RLS) policies để bảo vệ data theo user/brain owner.

## Implementation Steps

### 4.1 Enable RLS
```sql
ALTER TABLE brains ENABLE ROW LEVEL SECURITY;
ALTER TABLE neurons ENABLE ROW LEVEL SECURITY;
ALTER TABLE neuron_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE synapses ENABLE ROW LEVEL SECURITY;
ALTER TABLE fibers ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiber_neurons ENABLE ROW LEVEL SECURITY;
ALTER TABLE typed_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE cognitive_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE hot_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gaps ENABLE ROW LEVEL SECURITY;
```

### 4.2 RLS Policies (Brain-level isolation)
```sql
-- Brains: owner can CRUD their own brains
CREATE POLICY "Users manage own brains"
  ON brains FOR ALL
  USING (owner_id = auth.uid()::text);

-- Public brains: anyone can read
CREATE POLICY "Public brains readable"
  ON brains FOR SELECT
  USING (is_public = true);

-- All other tables: cascade from brain ownership
CREATE POLICY "Brain owner accesses neurons"
  ON neurons FOR ALL
  USING (brain_id IN (
    SELECT id FROM brains WHERE owner_id = auth.uid()::text
  ));

-- (Repeat for each table)
```

### 4.3 Service Role Key (for MCP server)
- [ ] Dùng `service_role` key trong MCP server → bypass RLS
- [ ] Anon key cho dashboard/client → RLS enforced
- [ ] Lý do: MCP server chạy trusted, cần full access

## Priority
🟡 **OPTIONAL cho MVP** — Nếu chỉ 1 user (anh) dùng, có thể skip RLS ban đầu và dùng `service_role` key trực tiếp. Thêm RLS sau khi cần multi-user.

## Test Criteria
- [ ] Service role key: CRUD hoạt động bình thường
- [ ] Anon key + RLS: chỉ thấy data của mình
- [ ] Thử access brain của user khác → bị blocked

---
Next Phase: [phase-05-mcp-test.md](./phase-05-mcp-test.md)
