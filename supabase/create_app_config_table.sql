CREATE TABLE IF NOT EXISTS app_config (
    key   text PRIMARY KEY,
    value text NOT NULL,
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE app_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON app_config
    FOR SELECT USING (true);

CREATE POLICY "Service write access" ON app_config
    FOR ALL USING (auth.role() = 'service_role');
