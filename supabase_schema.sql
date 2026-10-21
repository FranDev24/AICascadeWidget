-- ============================================================================
-- AICascade Widget - Supabase Schema  (v3 · hardened · idempotente)
-- Proyecto: qicspclpqyvjskgqwnru
-- Ejecutar en: Supabase Dashboard > SQL Editor
--
-- Diseño de seguridad:
--   * service_role es el UNICO rol con acceso (bypassa RLS, pero los GRANTs
--     limitan el acceso SQL). anon/authenticated no tienen privilegios.
--   * vault_keys jamas se expone por la Data API: credenciales solo en el
--     backend. Para secretos a largo plazo, valorar Supabase Vault.
--   * Vistas con security_invoker = true: respetan permisos del invocador.
-- ============================================================================


-- ============================================================================
-- 0. LIMPIEZA DE POLICIES PERMISIVAS HEREDADAS (migracion)
-- ============================================================================
DROP POLICY IF EXISTS "Allow read access to cascade_logs"       ON public.cascade_logs;
DROP POLICY IF EXISTS "Allow insert to cascade_logs"            ON public.cascade_logs;
DROP POLICY IF EXISTS "Allow read active vault_keys"            ON public.vault_keys;
DROP POLICY IF EXISTS "Allow upsert vault_keys"                 ON public.vault_keys;
DROP POLICY IF EXISTS "Allow update vault_keys"                 ON public.vault_keys;
DROP POLICY IF EXISTS "Allow all cascade_sessions"              ON public.cascade_sessions;
DROP POLICY IF EXISTS "Allow read provider_metrics"             ON public.provider_metrics;
DROP POLICY IF EXISTS "Allow insert provider_metrics"           ON public.provider_metrics;
DROP POLICY IF EXISTS "Allow update provider_metrics"           ON public.provider_metrics;


-- ============================================================================
-- 1. cascade_logs - telemetria de failover
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.cascade_logs (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_from      TEXT NOT NULL,
    model_to        TEXT NOT NULL,
    reason          TEXT NOT NULL
                    CHECK (reason IN ('quota_exceeded','error','manual','failback','rate_limit','timeout','simulated')),
    tokens_remaining BIGINT NOT NULL DEFAULT 0 CHECK (tokens_remaining >= 0),
    tier_from       SMALLINT NOT NULL CHECK (tier_from BETWEEN 1 AND 3),
    tier_to         SMALLINT NOT NULL CHECK (tier_to BETWEEN 1 AND 3),
    session_id      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_cascade_logs_created_at ON public.cascade_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_session_id ON public.cascade_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_model_to   ON public.cascade_logs (model_to);
CREATE INDEX IF NOT EXISTS idx_cascade_logs_reason     ON public.cascade_logs (reason);
-- Soporte de la subconsulta "ultimo cambio" de la vista (ver seccion 6)
CREATE INDEX IF NOT EXISTS idx_cascade_logs_latest
    ON public.cascade_logs (created_at DESC, id DESC);

DO $$
BEGIN
    UPDATE public.cascade_logs SET metadata        = '{}'::jsonb WHERE metadata IS NULL;
    UPDATE public.cascade_logs SET tokens_remaining = 0            WHERE tokens_remaining IS NULL;
END $$;
DO $$ BEGIN ALTER TABLE public.cascade_logs ALTER COLUMN tokens_remaining SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.cascade_logs ALTER COLUMN metadata        SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;

ALTER TABLE public.cascade_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "svc_read_cascade_logs" ON public.cascade_logs;
CREATE POLICY "svc_read_cascade_logs"  ON public.cascade_logs FOR SELECT TO service_role USING (true);
DROP POLICY IF EXISTS "svc_insert_cascade_logs" ON public.cascade_logs;
CREATE POLICY "svc_insert_cascade_logs" ON public.cascade_logs FOR INSERT TO service_role WITH CHECK (true);

REVOKE ALL ON TABLE public.cascade_logs FROM PUBLIC, anon, authenticated;
GRANT  SELECT, INSERT ON TABLE public.cascade_logs TO service_role;
REVOKE ALL ON SEQUENCE public.cascade_logs_id_seq FROM PUBLIC, anon, authenticated;
GRANT  USAGE, SELECT ON SEQUENCE public.cascade_logs_id_seq TO service_role;


-- ============================================================================
-- 2. vault_keys - credenciales (SOLO backend)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.vault_keys (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider    TEXT UNIQUE NOT NULL,
    api_key     TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    usage_count BIGINT NOT NULL DEFAULT 0 CHECK (usage_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_vault_keys_is_active ON public.vault_keys (is_active);

-- Reconciliar el CHECK de provider (amplia a todos los usados por la app)
DO $$
DECLARE cname TEXT;
BEGIN
    SELECT conname INTO cname
      FROM pg_constraint
     WHERE conrelid = 'public.vault_keys'::regclass
       AND contype = 'c'
       AND conname LIKE '%provider%';
    IF cname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.vault_keys DROP CONSTRAINT %I', cname);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.vault_keys'::regclass
                      AND conname  = 'vault_keys_provider_check') THEN
        ALTER TABLE public.vault_keys
            ADD CONSTRAINT vault_keys_provider_check
            CHECK (provider IN ('openai','anthropic','google','ollama',
                                'deepseek','openrouter','groq','meta','xai'));
    END IF;
END $$;

DO $$ BEGIN ALTER TABLE public.vault_keys ALTER COLUMN usage_count SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.vault_keys ALTER COLUMN is_active   SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;

ALTER TABLE public.vault_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "svc_read_vault_keys" ON public.vault_keys;
CREATE POLICY "svc_read_vault_keys" ON public.vault_keys FOR SELECT TO service_role USING (true);
DROP POLICY IF EXISTS "svc_write_vault_keys" ON public.vault_keys;
CREATE POLICY "svc_write_vault_keys" ON public.vault_keys FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON TABLE public.vault_keys FROM PUBLIC, anon, authenticated;
GRANT  ALL ON TABLE public.vault_keys TO service_role;
REVOKE ALL ON SEQUENCE public.vault_keys_id_seq FROM PUBLIC, anon, authenticated;
GRANT  USAGE, SELECT ON SEQUENCE public.vault_keys_id_seq TO service_role;


-- ============================================================================
-- 3. cascade_sessions - estado de sesiones
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.cascade_sessions (
    id               BIGSERIAL PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id       TEXT UNIQUE NOT NULL,
    active_model     TEXT,
    active_tier      SMALLINT CHECK (active_tier BETWEEN 1 AND 3),
    total_tokens_used BIGINT NOT NULL DEFAULT 0 CHECK (total_tokens_used >= 0),
    total_switches   INT  NOT NULL DEFAULT 0 CHECK (total_switches   >= 0),
    total_calls      INT  NOT NULL DEFAULT 0 CHECK (total_calls      >= 0),
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','completed','failed')),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_cascade_sessions_status ON public.cascade_sessions (status);

DO $$
BEGIN
    UPDATE public.cascade_sessions SET metadata          = '{}'::jsonb WHERE metadata IS NULL;
    UPDATE public.cascade_sessions SET total_tokens_used = 0 WHERE total_tokens_used IS NULL;
    UPDATE public.cascade_sessions SET total_switches    = 0 WHERE total_switches    IS NULL;
    UPDATE public.cascade_sessions SET total_calls       = 0 WHERE total_calls       IS NULL;
    UPDATE public.cascade_sessions SET status            = 'active' WHERE status IS NULL;
END $$;
DO $$ BEGIN ALTER TABLE public.cascade_sessions ALTER COLUMN total_tokens_used SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.cascade_sessions ALTER COLUMN total_switches    SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.cascade_sessions ALTER COLUMN total_calls       SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.cascade_sessions ALTER COLUMN status            SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.cascade_sessions ALTER COLUMN metadata          SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;

ALTER TABLE public.cascade_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "svc_all_cascade_sessions" ON public.cascade_sessions;
CREATE POLICY "svc_all_cascade_sessions" ON public.cascade_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON TABLE public.cascade_sessions FROM PUBLIC, anon, authenticated;
GRANT  ALL ON TABLE public.cascade_sessions TO service_role;
REVOKE ALL ON SEQUENCE public.cascade_sessions_id_seq FROM PUBLIC, anon, authenticated;
GRANT  USAGE, SELECT ON SEQUENCE public.cascade_sessions_id_seq TO service_role;


-- ============================================================================
-- 4. provider_metrics - metricas agregadas
--    Nota: UNIQUE(date, provider, model) ya indexa por (date, provider, model);
--    no se crea idx_provider_metrics_date (redundante).
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.provider_metrics (
    id               BIGSERIAL PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date             DATE NOT NULL DEFAULT CURRENT_DATE,  -- zona horaria de sesion
    provider         TEXT NOT NULL,
    model            TEXT NOT NULL,
    tier             SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
    calls_count      BIGINT NOT NULL DEFAULT 0 CHECK (calls_count      >= 0),
    tokens_used      BIGINT NOT NULL DEFAULT 0 CHECK (tokens_used      >= 0),
    tokens_remaining BIGINT NOT NULL DEFAULT 0 CHECK (tokens_remaining >= 0),
    errors_count     BIGINT NOT NULL DEFAULT 0 CHECK (errors_count     >= 0),
    avg_latency_ms   NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (avg_latency_ms >= 0),
    UNIQUE (date, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_provider_metrics_provider ON public.provider_metrics (provider);

DO $$
BEGIN
    UPDATE public.provider_metrics SET calls_count      = 0 WHERE calls_count      IS NULL;
    UPDATE public.provider_metrics SET tokens_used      = 0 WHERE tokens_used      IS NULL;
    UPDATE public.provider_metrics SET tokens_remaining = 0 WHERE tokens_remaining IS NULL;
    UPDATE public.provider_metrics SET errors_count     = 0 WHERE errors_count     IS NULL;
    UPDATE public.provider_metrics SET avg_latency_ms   = 0 WHERE avg_latency_ms   IS NULL;
END $$;
DO $$ BEGIN ALTER TABLE public.provider_metrics ALTER COLUMN calls_count      SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.provider_metrics ALTER COLUMN tokens_used      SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.provider_metrics ALTER COLUMN tokens_remaining SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.provider_metrics ALTER COLUMN errors_count     SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE public.provider_metrics ALTER COLUMN avg_latency_ms   SET NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;

ALTER TABLE public.provider_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "svc_read_provider_metrics" ON public.provider_metrics;
CREATE POLICY "svc_read_provider_metrics"  ON public.provider_metrics FOR SELECT TO service_role USING (true);
DROP POLICY IF EXISTS "svc_insert_provider_metrics" ON public.provider_metrics;
CREATE POLICY "svc_insert_provider_metrics" ON public.provider_metrics FOR INSERT TO service_role WITH CHECK (true);
DROP POLICY IF EXISTS "svc_update_provider_metrics" ON public.provider_metrics;
CREATE POLICY "svc_update_provider_metrics" ON public.provider_metrics FOR UPDATE TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON TABLE public.provider_metrics FROM PUBLIC, anon, authenticated;
GRANT  SELECT, INSERT, UPDATE ON TABLE public.provider_metrics TO service_role;
REVOKE ALL ON SEQUENCE public.provider_metrics_id_seq FROM PUBLIC, anon, authenticated;
GRANT  USAGE, SELECT ON SEQUENCE public.provider_metrics_id_seq TO service_role;


-- ============================================================================
-- 5. FUNCTION + TRIGGERS (updated_at automatico)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vault_keys_updated_at ON public.vault_keys;
CREATE TRIGGER trg_vault_keys_updated_at
    BEFORE UPDATE ON public.vault_keys
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trg_cascade_sessions_updated_at ON public.cascade_sessions;
CREATE TRIGGER trg_cascade_sessions_updated_at
    BEFORE UPDATE ON public.cascade_sessions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


-- ============================================================================
-- 6. VIEWS (security_invoker = true + DROP previo para idempotencia de columnas)
-- ============================================================================
DROP VIEW IF EXISTS public.cascade_telemetry_summary;
CREATE VIEW public.cascade_telemetry_summary
WITH (security_invoker = true) AS
SELECT
    COUNT(*)                                                              AS total_switches,
    COUNT(*) FILTER (WHERE l.created_at >= CURRENT_DATE)                  AS switches_today,
    MAX(l.created_at)                                                     AS last_switch_at,
    COALESCE(SUM(l.tokens_remaining), 0)                                  AS total_tokens_remaining,
    latest.model_to                                                       AS current_model,
    latest.tier_to                                                        AS current_tier
FROM public.cascade_logs AS l
LEFT JOIN LATERAL (
    SELECT c.model_to, c.tier_to
      FROM public.cascade_logs AS c
     ORDER BY c.created_at DESC, c.id DESC
     LIMIT 1
) AS latest ON true;

DROP VIEW IF EXISTS public.vault_status;
CREATE VIEW public.vault_status
WITH (security_invoker = true) AS
SELECT
    v.provider,
    v.is_active,
    v.created_at,
    v.last_used_at,
    v.usage_count,
    CASE WHEN v.api_key IS NOT NULL AND v.api_key <> '' THEN true ELSE false END AS has_key
FROM public.vault_keys AS v
WHERE v.is_active = true;

REVOKE ALL ON public.cascade_telemetry_summary FROM PUBLIC, anon, authenticated;
GRANT  SELECT ON public.cascade_telemetry_summary TO service_role;
REVOKE ALL ON public.vault_status FROM PUBLIC, anon, authenticated;
GRANT  SELECT ON public.vault_status TO service_role;


-- ============================================================================
-- 7. Limpieza de indices redundantes (los crea UNIQUE, no el script)
-- ============================================================================
DROP INDEX IF EXISTS public.idx_vault_keys_provider;
DROP INDEX IF EXISTS public.idx_cascade_sessions_session_id;


-- ============================================================================
-- AUDITORIA (ejecutar aparte)
--   SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public';
--   SELECT tablename, policyname, roles FROM pg_policies WHERE schemaname='public';
-- ============================================================================
