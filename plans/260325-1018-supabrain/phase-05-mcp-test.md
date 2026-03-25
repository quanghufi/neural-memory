# Phase 05: MCP Integration Test
Status: ⬜ Pending
Dependencies: Phase 03

## Objective
Verify tất cả core MCP tools hoạt động với Supabase PostgreSQL backend.

## Test Matrix

### Core Tools (must pass)
| Tool | Test | Expected |
|------|------|----------|
| `nmem_remember` | Lưu "Test fact about Supabase" | Success, fiber_id returned |
| `nmem_recall` | Query "Supabase" | Returns stored memory |
| `nmem_context` | Load recent memories | Shows test memory |
| `nmem_health` | Brain health check | No errors |
| `nmem_stats` | Memory statistics | Shows 1+ memories |
| `nmem_todo` | Add todo item | Success |
| `nmem_session` | Set/get session | Success |

### Extended Tools (should pass)
| Tool | Test | Expected |
|------|------|----------|
| `nmem_hypothesize` | Create hypothesis | Success |
| `nmem_evidence` | Add evidence | Success |
| `nmem_predict` | Create prediction | Success |
| `nmem_consolidate` | Run consolidation | No errors |
| `nmem_recall` depth=2 | Deep recall | Spreading activation works |
| `nmem_train` | Train from docs | Success |

### Performance Benchmarks
| Operation | SQLite Local | Supabase Target | Acceptable? |
|-----------|-------------|-----------------|-------------|
| remember | <100ms | <500ms | ✅ |
| recall | <200ms | <1000ms | ✅ |
| context | <100ms | <500ms | ✅ |

## Implementation Steps
1. [ ] Start MCP server with Supabase config
2. [ ] Run core tools test suite
3. [ ] Run extended tools test suite
4. [ ] Measure latency for each operation
5. [ ] Record any failures/issues
6. [ ] Fix issues if any

## Test Criteria
- [ ] All core tools pass
- [ ] >80% extended tools pass
- [ ] Latency < 1s for common operations
- [ ] No data corruption
- [ ] Brain data visible in Supabase Table Editor

---
Next Phase: [phase-06-verify-docs.md](./phase-06-verify-docs.md)
