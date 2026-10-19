-- AICascade Widget - Supabase Database Schema
-- ============================================
-- Run this in your Supabase Dashboard SQL Editor
-- https://supabase.com/dashboard/project/_/sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLE: cascade_logs
-- Stores model failover events for telemetry
-- ============================================
CREATE TABLE IF NOT EXISTS cascade_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    model_from TEXT NOT NULL,
    model_to TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('quota_exceeded', 'error', 'manual', 'failback', 'rate_limit', 'timeout', 'simulated')),
    tokens_remaining BIGINT DEFAULT 0 NOT NULL CHECK (tokens_remaining >= 0),
    tier_from SMALLINT NOT NULL CHECK (tier_from BETWEEN 1 AND 3),
    tier_to SMALLINT NOT NULL CHECK (tier_to BETWEEN 1 AND 3),
    session_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for cascade_logs
CREATE INDEX IF NOT EXISTS idx_cascade_logs_created_at ON cascade_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_session_id ON cascade_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_model_to ON cascade_logs (model_to);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_reason ON cascade_logs (reason);

-- Enable Row Level Security
ALTER TABLE cascade_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Allow read access to all (adjust for production)
CREATE POLICY "Allow read access to cascade_logs" ON cascade_logs
    FOR SELECT USING (true);

-- Policy: Allow insert for authenticated users (or service role)
CREATE POLICY "Allow insert to cascade_logs" ON cascade_logs
    FOR INSERT WITH CHECK (true);

-- ============================================
-- TABLE: vault_keys
-- Stores encrypted API keys for providers
-- ============================================
CREATE TABLE IF NOT EXISTS vault_keys (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    provider TEXT UNIQUE NOT NULL CHECK (provider IN ('openai', 'anthropic', 'google', 'ollama', 'deepseek')),
    api_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    last_used_at TIMESTAMPTZ,
    usage_count BIGINT DEFAULT 0 NOT NULL
);

-- Index for vault_keys
CREATE INDEX IF NOT EXISTS idx_vault_keys_provider ON vault_keys (provider);
CREATE INDEX IF NOT EXISTS idx_vault_keys_is_active ON vault_keys (is_active);

-- Enable Row Level Security
ALTER TABLE vault_keys ENABLE ROW LEVEL SECURITY;

-- Policy: Allow read access to active keys only
CREATE POLICY "Allow read active vault_keys" ON vault_keys
    FOR SELECT USING (is_active = true);

-- Policy: Allow upsert for service role
CREATE POLICY "Allow upsert vault_keys" ON vault_keys
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow update vault_keys" ON vault_keys
    FOR UPDATE USING (true);

-- ============================================
-- TABLE: cascade_sessions
-- Tracks active sessions and their state
-- ============================================
CREATE TABLE IF NOT EXISTS cascade_sessions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    active_model TEXT,
    active_tier SMALLINT CHECK (active_tier BETWEEN 1 AND 3),
    total_tokens_used BIGINT DEFAULT 0,
    total_switches INT DEFAULT 0,
    total_calls INT DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed')),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_cascade_sessions_session_id ON cascade_sessions (session_id);
CREATE INDEX IF NOT EXISTS idx_cascade_sessions_status ON cascade_sessions (status);

ALTER TABLE cascade_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all cascade_sessions" ON cascade_sessions
    FOR ALL USING (true);

-- ============================================
-- TABLE: provider_metrics
-- Aggregated metrics per provider
-- ============================================
CREATE TABLE IF NOT EXISTS provider_metrics (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tier SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
    calls_count BIGINT DEFAULT 0,
    tokens_used BIGINT DEFAULT 0,
    tokens_remaining BIGINT DEFAULT 0,
    errors_count BIGINT DEFAULT 0,
    avg_latency_ms NUMERIC(10,2) DEFAULT 0,
    UNIQUE(date, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_provider_metrics_date ON provider_metrics (date DESC);
CREATE INDEX IF NOT EXISTS idx_provider_metrics_provider ON provider_metrics (provider);

ALTER TABLE provider_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read provider_metrics" ON provider_metrics
    FOR SELECT USING (true);

CREATE POLICY "Allow insert provider_metrics" ON provider_metrics
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow update provider_metrics" ON provider_metrics
    FOR UPDATE USING (true);

-- ============================================
-- FUNCTION: update_updated_at_column
-- Auto-update updated_at timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for vault_keys
DROP TRIGGER IF EXISTS update_vault_keys_updated_at ON vault_keys;
CREATE TRIGGER update_vault_keys_updated_at
    BEFORE UPDATE ON vault_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for cascade_sessions
DROP TRIGGER IF EXISTS update_cascade_sessions_updated_at ON cascade_sessions;
CREATE TRIGGER update_cascade_sessions_updated_at
    BEFORE UPDATE ON cascade_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEW: cascade_telemetry_summary
-- Real-time telemetry aggregation
-- ============================================
CREATE OR REPLACE VIEW cascade_telemetry_summary AS
SELECT
    COUNT(*) as total_switches,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as switches_today,
    MAX(created_at) as last_switch_at,
    (SELECT model_to FROM cascade_logs ORDER BY created_at DESC LIMIT 1) as current_model,
    (SELECT tier_to FROM cascade_logs ORDER BY created_at DESC LIMIT 1) as current_tier,
    SUM(tokens_remaining) as total_tokens_remaining
FROM cascade_logs;

-- ============================================
-- VIEW: vault_status
-- Current vault configuration status
-- ============================================
CREATE OR REPLACE VIEW vault_status AS
SELECT
    provider,
    is_active,
    created_at,
    last_used_at,
    usage_count,
    CASE WHEN api_key IS NOT NULL AND api_key != '' THEN true ELSE false END as has_key
FROM vault_keys
WHERE is_active = true
ORDER BY provider;

-- ============================================
-- GRANT PERMISSIONS (for service role)
-- ============================================
-- These are automatically handled by Supabase for service role
-- But explicit grants for clarity:
GRANT ALL ON cascade_logs TO service_role;
GRANT ALL ON vault_keys TO service_role;
GRANT ALL ON cascade_sessions TO service_role;
GRANT ALL ON provider_metrics TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;