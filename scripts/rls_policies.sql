-- ============================================================
-- SupaBrain: Row Level Security Policies
-- Run AFTER deploy_schema.sql
-- Optional: Skip for single-user MVP
-- ============================================================

-- Enable RLS on all tables
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

-- Brain owner policies
CREATE POLICY "Users manage own brains"
    ON brains FOR ALL
    USING (owner_id = auth.uid()::text);

CREATE POLICY "Public brains readable"
    ON brains FOR SELECT
    USING (is_public = true);

-- Cascade policies (all tables use brain_id FK)
CREATE POLICY "Brain owner accesses neurons"
    ON neurons FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses neuron_states"
    ON neuron_states FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses synapses"
    ON synapses FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses fibers"
    ON fibers FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses fiber_neurons"
    ON fiber_neurons FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses typed_memories"
    ON typed_memories FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses projects"
    ON projects FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses cognitive_state"
    ON cognitive_state FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses hot_index"
    ON hot_index FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));

CREATE POLICY "Brain owner accesses knowledge_gaps"
    ON knowledge_gaps FOR ALL
    USING (brain_id IN (SELECT id FROM brains WHERE owner_id = auth.uid()::text));
