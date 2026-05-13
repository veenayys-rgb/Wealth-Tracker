-- ══════════════════════════════════════════════════════════════
-- WEALTH TRACKER — HOLDINGS TABLES (run in Supabase SQL Editor)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cfg_equity_india (
    id            BIGSERIAL PRIMARY KEY,
    isin          TEXT,
    company_name  TEXT,
    symbol        TEXT,
    holding_type  TEXT,
    source        TEXT,
    buy_date      TEXT,
    qty           NUMERIC(18,4),
    avg_cost      NUMERIC(18,4)
);

CREATE TABLE IF NOT EXISTS cfg_equity_international (
    id        BIGSERIAL PRIMARY KEY,
    name      TEXT,
    symbol    TEXT,
    isin      TEXT,
    region    TEXT,
    exchange  TEXT,
    currency  TEXT,
    source    TEXT,
    buy_date  TEXT,
    qty       NUMERIC(18,4),
    avg_cost  NUMERIC(18,4)
);

CREATE TABLE IF NOT EXISTS cfg_mutual_funds (
    id        BIGSERIAL PRIMARY KEY,
    owner     TEXT,
    folio_no  TEXT,
    isin      TEXT,
    fund_name TEXT,
    units     NUMERIC(18,4),
    avg_nav   NUMERIC(18,4)
);

CREATE TABLE IF NOT EXISTS cfg_watchlist (
    id            BIGSERIAL PRIMARY KEY,
    isin          TEXT,
    symbol        TEXT,
    company_name  TEXT,
    region        TEXT,
    currency      TEXT
);

CREATE TABLE IF NOT EXISTS cfg_bank_india (
    id                BIGSERIAL PRIMARY KEY,
    bank_name         TEXT,
    account_type      TEXT,
    account_no_last4  TEXT,
    ifsc              TEXT,
    owner             TEXT,
    second_holder     TEXT,
    balance           NUMERIC(18,2)
);

CREATE TABLE IF NOT EXISTS cfg_bank_uae (
    id            BIGSERIAL PRIMARY KEY,
    bank_name     TEXT,
    currency      TEXT,
    account_type  TEXT,
    account_no    TEXT,
    owner         TEXT,
    balance_aed   NUMERIC(18,2)
);

CREATE TABLE IF NOT EXISTS cfg_fixed_deposits (
    id               BIGSERIAL PRIMARY KEY,
    bank             TEXT,
    fd_no            TEXT,
    owner            TEXT,
    currency         TEXT,
    amount           NUMERIC(18,2),
    rate_pa          NUMERIC(8,4),
    start_date       TEXT,
    maturity_date    TEXT,
    maturity_amount  NUMERIC(18,2)
);

CREATE TABLE IF NOT EXISTS cfg_insurance (
    id                    BIGSERIAL PRIMARY KEY,
    company_name          TEXT,
    insurance_type        TEXT,
    policy_no             TEXT,
    owner                 TEXT,
    beneficiary           TEXT,
    currency              TEXT,
    insured_value         NUMERIC(18,2),
    surrender_value       NUMERIC(18,2),
    premium_amount        NUMERIC(18,2),
    premium_payment_term  TEXT,
    years_paid            TEXT,
    premium_paid_ytd      NUMERIC(18,2),
    next_premium_due      TEXT,
    maturity_date         TEXT
);

-- Enable RLS
ALTER TABLE cfg_equity_india         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_equity_international ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_mutual_funds         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_watchlist            ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_bank_india           ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_bank_uae             ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_fixed_deposits       ENABLE ROW LEVEL SECURITY;
ALTER TABLE cfg_insurance            ENABLE ROW LEVEL SECURITY;

-- Full access for anon (personal app — anon key is in private secrets)
CREATE POLICY "anon_all" ON cfg_equity_india         FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_equity_international FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_mutual_funds         FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_watchlist            FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_bank_india           FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_bank_uae             FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_fixed_deposits       FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all" ON cfg_insurance            FOR ALL TO anon USING (true) WITH CHECK (true);
