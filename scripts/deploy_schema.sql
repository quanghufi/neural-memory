-- ============================================================
-- SupaBrain: Neural Memory PostgreSQL Schema for Supabase
-- Generated from neural-memory v0.x postgres_schema.py
-- Run this in Supabase SQL Editor (https://supabase.com)
-- ============================================================

-- Step 1: Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Brains table
CREATE TABLE IF NOT EXISTS brains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    owner_id TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    shared_with JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- Step 3: Neurons with pgvector embedding + tsvector FTS
CREATE TABLE IF NOT EXISTS neurons (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    content_hash BIGINT DEFAULT 0,
    content_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', content)
    ) STORED,
    embedding vector(384),
    device_id TEXT DEFAULT '',
    device_origin TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_neurons_type ON neurons(brain_id, type);
CREATE INDEX IF NOT EXISTS idx_neurons_created ON neurons(brain_id, created_at);
CREATE INDEX IF NOT EXISTS idx_neurons_hash ON neurons(brain_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_neurons_fts ON neurons USING GIN(content_tsv);

-- Step 4: Neuron states
CREATE TABLE IF NOT EXISTS neuron_states (
    neuron_id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    activation_level DOUBLE PRECISION DEFAULT 0.0,
    access_frequency INTEGER DEFAULT 0,
    last_activated TIMESTAMPTZ,
    decay_rate DOUBLE PRECISION DEFAULT 0.1,
    firing_threshold DOUBLE PRECISION DEFAULT 0.3,
    refractory_until TIMESTAMPTZ,
    refractory_period_ms DOUBLE PRECISION DEFAULT 500.0,
    homeostatic_target DOUBLE PRECISION DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brain_id, neuron_id),
    FOREIGN KEY (brain_id, neuron_id) REFERENCES neurons(brain_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_neuron_states_freq ON neuron_states(brain_id, access_frequency DESC);

-- Step 5: Synapses
CREATE TABLE IF NOT EXISTS synapses (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,
    weight DOUBLE PRECISION DEFAULT 0.5,
    direction TEXT DEFAULT 'uni',
    metadata JSONB DEFAULT '{}',
    reinforced_count INTEGER DEFAULT 0,
    last_activated TIMESTAMPTZ,
    device_id TEXT DEFAULT '',
    device_origin TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE,
    FOREIGN KEY (brain_id, source_id) REFERENCES neurons(brain_id, id) ON DELETE CASCADE,
    FOREIGN KEY (brain_id, target_id) REFERENCES neurons(brain_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_synapses_source ON synapses(brain_id, source_id);
CREATE INDEX IF NOT EXISTS idx_synapses_target ON synapses(brain_id, target_id);
CREATE INDEX IF NOT EXISTS idx_synapses_pair ON synapses(brain_id, source_id, target_id);

-- Step 6: Fibers
CREATE TABLE IF NOT EXISTS fibers (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    neuron_ids JSONB NOT NULL,
    synapse_ids JSONB NOT NULL,
    anchor_neuron_id TEXT NOT NULL,
    pathway JSONB DEFAULT '[]',
    conductivity DOUBLE PRECISION DEFAULT 1.0,
    last_conducted TIMESTAMPTZ,
    time_start TIMESTAMPTZ,
    time_end TIMESTAMPTZ,
    coherence DOUBLE PRECISION DEFAULT 0.0,
    salience DOUBLE PRECISION DEFAULT 0.0,
    frequency INTEGER DEFAULT 0,
    summary TEXT,
    tags JSONB DEFAULT '[]',
    auto_tags JSONB DEFAULT '[]',
    agent_tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    compression_tier INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,
    device_id TEXT DEFAULT '',
    device_origin TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fibers_created ON fibers(brain_id, created_at);
CREATE INDEX IF NOT EXISTS idx_fibers_salience ON fibers(brain_id, salience);
CREATE INDEX IF NOT EXISTS idx_fibers_conductivity ON fibers(brain_id, conductivity);

-- Step 7: Fiber-neuron junction
CREATE TABLE IF NOT EXISTS fiber_neurons (
    brain_id TEXT NOT NULL,
    fiber_id TEXT NOT NULL,
    neuron_id TEXT NOT NULL,
    PRIMARY KEY (brain_id, fiber_id, neuron_id),
    FOREIGN KEY (brain_id, fiber_id) REFERENCES fibers(brain_id, id) ON DELETE CASCADE,
    FOREIGN KEY (brain_id, neuron_id) REFERENCES neurons(brain_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fiber_neurons_neuron ON fiber_neurons(brain_id, neuron_id);

-- Step 8: Typed memories
CREATE TABLE IF NOT EXISTS typed_memories (
    fiber_id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    provenance JSONB NOT NULL,
    expires_at TIMESTAMPTZ,
    project_id TEXT,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    trust_score DOUBLE PRECISION DEFAULT NULL,
    source TEXT DEFAULT NULL,
    PRIMARY KEY (brain_id, fiber_id),
    FOREIGN KEY (brain_id, fiber_id) REFERENCES fibers(brain_id, id) ON DELETE CASCADE,
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_typed_memories_type ON typed_memories(brain_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_typed_memories_project ON typed_memories(brain_id, project_id);
CREATE INDEX IF NOT EXISTS idx_typed_memories_expires ON typed_memories(brain_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_typed_memories_trust ON typed_memories(brain_id, trust_score);

-- Step 9: Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    tags JSONB DEFAULT '[]',
    priority DOUBLE PRECISION DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brain_id, id),
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(brain_id, name);

-- Step 10: Cognitive state (hypothesis/prediction tracking)
CREATE TABLE IF NOT EXISTS cognitive_state (
    neuron_id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.5,
    evidence_for_count INTEGER DEFAULT 0,
    evidence_against_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
        CHECK (status IN ('active', 'confirmed', 'refuted', 'superseded', 'pending', 'expired')),
    predicted_at TEXT,
    resolved_at TEXT,
    schema_version INTEGER DEFAULT 1,
    parent_schema_id TEXT,
    last_evidence_at TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, neuron_id)
);

CREATE INDEX IF NOT EXISTS idx_cognitive_confidence ON cognitive_state(brain_id, confidence);
CREATE INDEX IF NOT EXISTS idx_cognitive_status ON cognitive_state(brain_id, status);

-- Step 11: Hot index (ranked cognitive summary)
CREATE TABLE IF NOT EXISTS hot_index (
    brain_id TEXT NOT NULL,
    slot INTEGER NOT NULL,
    category TEXT NOT NULL,
    neuron_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    score DOUBLE PRECISION NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, slot)
);

-- Step 12: Knowledge gaps (metacognition)
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id TEXT PRIMARY KEY,
    brain_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    detection_source TEXT NOT NULL,
    related_neuron_ids TEXT DEFAULT '[]',
    resolved_at TEXT,
    resolved_by_neuron_id TEXT,
    priority DOUBLE PRECISION DEFAULT 0.5
);

CREATE INDEX IF NOT EXISTS idx_gaps_brain ON knowledge_gaps(brain_id);
CREATE INDEX IF NOT EXISTS idx_gaps_priority ON knowledge_gaps(brain_id, priority);

-- ============================================================
-- DONE! Verify: SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' ORDER BY table_name;
-- ============================================================
