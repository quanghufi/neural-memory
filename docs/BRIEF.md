# 💡 BRIEF: SupaBrain — Neural Memory trên Supabase

**Ngày tạo:** 2026-03-25
**Loại sản phẩm:** Web App (MCP Server + REST API + Dashboard)

---

## 1. VẤN ĐỀ CẦN GIẢI QUYẾT

Neural Memory hiện dùng **SQLite local** → data bị lock trên 1 máy. Cloud sync qua Cloudflare Worker phải tự host.

**Mong muốn:** Một hệ thống "brain" tương tự neural-memory nhưng **lưu trực tiếp trên Supabase (PostgreSQL)** → free, không cần tự host, multi-device sẵn.

## 2. GIẢI PHÁP ĐỀ XUẤT

Xây dựng **SupaBrain** — bản neural-memory lite lưu trên Supabase free tier:
- **Storage:** Supabase PostgreSQL thay SQLite
- **Auth:** Supabase Auth (miễn phí 50K MAUs)
- **Realtime:** Supabase Realtime cho multi-device sync
- **API:** Supabase Edge Functions hoặc self-host FastAPI
- **Interface:** MCP Server để tích hợp Claude/AI agents

## 3. ĐỐI TƯỢNG SỬ DỤNG

- **Primary:** Anh — AI developer cần persistent memory cho AI agents
- **Secondary:** Developers muốn free cloud brain storage

## 4. NGHIÊN CỨU

### Neural Memory — Kiến trúc tham khảo

| Thành phần | Mô tả | Áp dụng cho SupaBrain? |
|-----------|-------|----------------------|
| **Neuron** | Đơn vị thông tin (entity, concept, time…) | ✅ Giữ nguyên |
| **Synapse** | Kết nối giữa neurons (24 loại: CAUSED_BY, LEADS_TO…) | ✅ Giữ nguyên |
| **Fiber** | Pathway chứa memory content | ✅ Giữ nguyên |
| **Brain** | Container + config | ✅ Giữ nguyên |
| **TypedMemory** | 14 loại (fact, decision, todo…) | ✅ Giữ nguyên |
| **Spreading Activation** | Retrieval qua graph traversal | ⚠️ Simplified — dùng SQL recursive CTE |
| **MemoryEncoder** | Text → neural structures | ✅ Giữ, chạy client-side |
| **Consolidation** | Prune, merge, decay… | 🟡 Phase 2 |
| **Cognitive Layer** | Hypothesis, evidence, predictions | 🟡 Phase 2 |

### Supabase Free Tier Limits

| Resource | Limit | Đủ dùng? |
|----------|-------|----------|
| DB Storage | 500 MB | ✅ Đủ cho ~100K+ memories |
| API Requests | Unlimited | ✅ Không lo |
| MAUs | 50,000 | ✅ Quá dư |
| Bandwidth | 5 GB/mo | ✅ Text-based, rất nhẹ |
| Projects | 2 active | ⚠️ Chỉ 2 project free |
| Inactivity | Pause sau 7 ngày | ⚠️ Cần ping định kỳ |

### Điểm khác biệt so với Neural Memory gốc

| Neural Memory | SupaBrain |
|--------------|-----------|
| SQLite local | PostgreSQL cloud (Supabase) |
| Self-host sync server | Supabase Realtime built-in |
| Offline-first | Cloud-first, offline fallback |
| Cloudflare Worker sync | Không cần — direct DB |
| Python package | Python MCP + REST API |

## 5. TÍNH NĂNG

### 🚀 MVP (Bắt buộc có)

- [ ] **Database Schema** — Tables: brains, neurons, synapses, fibers, typed_memories
- [ ] **Core CRUD** — Tạo/đọc/sửa/xóa neurons, synapses, fibers
- [ ] **nmem_remember** — Lưu memory (auto-detect type)
- [ ] **nmem_recall** — Truy xuất memory bằng semantic search (FTS + graph traversal)
- [ ] **nmem_context** — Load recent context
- [ ] **Supabase Auth** — Đăng ký/đăng nhập, Row Level Security
- [ ] **MCP Server** — Tích hợp Claude Code / Gemini
- [ ] **Brain management** — Tạo/chọn/list brains

### 🎁 Phase 2 (Làm sau)

- [ ] Spreading Activation nâng cao (SQL recursive CTE)
- [ ] Consolidation engine (prune, merge, decay)
- [ ] Cognitive layer (hypothesis, evidence, predictions)
- [ ] Web Dashboard (React)
- [ ] Brain versioning (snapshot, rollback)
- [ ] Training pipeline (ingest PDF, DOCX…)
- [ ] Edge Functions cho server-side processing

### 💭 Backlog (Cân nhắc)

- [ ] VS Code extension
- [ ] Telegram backup
- [ ] Import adapters (ChromaDB, Mem0…)
- [ ] Real-time collaborative brains

## 6. ĐÁNH GIÁ KỸ THUẬT

### 🟢 DỄ LÀM
- Database schema trên Supabase (PostgreSQL tables)
- CRUD operations qua Supabase client
- Auth + RLS (Row Level Security)
- Basic MCP server wrapper

### 🟡 TRUNG BÌNH
- Semantic recall (Full-text search PostgreSQL + graph traversal)
- Memory encoder (text → neuron/synapse/fiber structures)
- Query parser + temporal extraction

### 🔴 KHÓ
- Spreading activation trên PostgreSQL (recursive CTE performance)
- Consolidation engine (complex async operations)
- Real-time sync giữa local cache + Supabase

### ⚠️ Rủi ro

| Rủi ro | Giải pháp |
|--------|----------|
| Supabase pause sau 7 ngày | Cron job ping định kỳ (free with GitHub Actions) |
| 500MB storage limit | Consolidation tự prune old data |
| Graph traversal chậm trên PostgreSQL | Cache hot paths, limit depth |
| Supabase outage | Local SQLite fallback (hybrid) |

## 7. TECH STACK DỰ KIẾN

| Layer | Technology |
|-------|-----------|
| Database | Supabase (PostgreSQL 15+) |
| Auth | Supabase Auth |
| Backend | Python + FastAPI (hoặc Edge Functions) |
| MCP Server | Python MCP SDK |
| Client | supabase-py (Python client) |
| Search | PostgreSQL FTS (tsvector) |
| Dashboard | React + Vite (Phase 2) |

## 8. BƯỚC TIẾP THEO

→ Chạy `/plan` để thiết kế chi tiết database schema + API
