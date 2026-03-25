# Plan: SupaBrain — Neural Memory on Supabase
Created: 2026-03-25T10:18:00+07:00
Status: 🟡 In Progress

## Overview
Fork neural-memory, cấu hình PostgreSQL storage trỏ về Supabase free tier.
Neural-memory đã có sẵn `PostgreSQLStorage` backend → chỉ cần:
1. Tạo Supabase project + chạy schema
2. Config connection string
3. Thêm RLS policies cho multi-user
4. Test qua MCP tools

## Approach: Fork + Adapt (Option 1)
- Giữ nguyên neural-memory codebase
- Chỉ thay connection params → Supabase PostgreSQL URL
- Thêm Supabase-specific features (Auth, RLS)
- Dễ merge upstream updates

## Tech Stack
- **Database:** Supabase PostgreSQL (free tier: 500MB)
- **Backend:** neural-memory Python package (existing)
- **Storage:** `PostgreSQLStorage` (existing in neural-memory)
- **Extensions:** pgvector (Supabase native), tsvector FTS
- **Auth:** Supabase Auth + RLS
- **MCP:** neural-memory MCP server (existing)

## Phases

| Phase | Name | Status | Progress |
|-------|------|--------|----------|
| 01 | Supabase Project Setup | ⬜ Pending | 0% |
| 02 | Database Schema Deploy | ⬜ Pending | 0% |
| 03 | Connection Config | ⬜ Pending | 0% |
| 04 | RLS + Auth Policies | ⬜ Pending | 0% |
| 05 | MCP Integration Test | ⬜ Pending | 0% |
| 06 | Verification & Docs | ⬜ Pending | 0% |

## Quick Commands
- Start Phase 1: `/code phase-01`
- Check progress: `/next`
- Save context: `/save-brain`
