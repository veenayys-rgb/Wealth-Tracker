-- Portfolio History table
-- Run this once in the Supabase SQL Editor

CREATE TABLE IF NOT EXISTS portfolio_history (
    id               bigint generated always as identity primary key,
    date             date   unique not null,
    shares_invested  numeric,
    shares_cv        numeric,
    mf_inv_vinay     numeric,
    mf_cv_vinay      numeric,
    mf_inv_harsh     numeric,
    mf_cv_harsh      numeric,
    mf_inv_anusha    numeric,
    mf_cv_anusha     numeric,
    total_invested   numeric,
    total_cv         numeric,
    gain_loss        numeric,
    return_pct       numeric
);

ALTER TABLE portfolio_history ENABLE ROW LEVEL SECURITY;

-- App (anon key) can read
CREATE POLICY "anon_read" ON portfolio_history
    FOR SELECT TO anon USING (true);

-- Fetcher (service key) can write
CREATE POLICY "service_write" ON portfolio_history
    FOR ALL TO service_role USING (true) WITH CHECK (true);
