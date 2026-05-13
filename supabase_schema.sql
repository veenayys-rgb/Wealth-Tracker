-- ══════════════════════════════════════════════════════════════
-- WEALTH TRACKER — SUPABASE SCHEMA
-- Run this in Supabase → SQL Editor → New Query → Run
-- ══════════════════════════════════════════════════════════════

-- 1. EQUITY INDIA PRICES (fetcher writes, Streamlit reads)
CREATE TABLE IF NOT EXISTS equity_india_prices (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL UNIQUE,
    price       NUMERIC(18,4),
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. EQUITY INTERNATIONAL PRICES
CREATE TABLE IF NOT EXISTS equity_international_prices (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL UNIQUE,
    region      TEXT,          -- UAE | US
    currency    TEXT,          -- AED | USD
    price       NUMERIC(18,4),
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. MF NAVs (includes ETFs)
CREATE TABLE IF NOT EXISTS mf_navs (
    id          BIGSERIAL PRIMARY KEY,
    isin        TEXT NOT NULL UNIQUE,
    nav         NUMERIC(18,4),
    nav_date    TEXT,
    amfi_name   TEXT,
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 4. FOREX RATES
CREATE TABLE IF NOT EXISTS forex_rates (
    id          BIGSERIAL PRIMARY KEY,
    pair        TEXT NOT NULL UNIQUE,  -- AED_INR | USD_INR
    rate        NUMERIC(18,6),
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 5. PORTFOLIO HISTORY
CREATE TABLE IF NOT EXISTS portfolio_history (
    id               BIGSERIAL PRIMARY KEY,
    date             DATE NOT NULL UNIQUE,
    shares_invested  NUMERIC(18,2) DEFAULT 0,
    shares_cv        NUMERIC(18,2) DEFAULT 0,
    mf_inv_vinay     NUMERIC(18,2) DEFAULT 0,
    mf_cv_vinay      NUMERIC(18,2) DEFAULT 0,
    mf_inv_harsh     NUMERIC(18,2) DEFAULT 0,
    mf_cv_harsh      NUMERIC(18,2) DEFAULT 0,
    mf_inv_anusha    NUMERIC(18,2) DEFAULT 0,
    mf_cv_anusha     NUMERIC(18,2) DEFAULT 0,
    total_invested   NUMERIC(18,2) DEFAULT 0,
    total_cv         NUMERIC(18,2) DEFAULT 0,
    gain_loss        NUMERIC(18,2) DEFAULT 0,
    return_pct       NUMERIC(8,4)  DEFAULT 0,
    recorded_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 6. WATCHLIST PRICES
CREATE TABLE IF NOT EXISTS watchlist_prices (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT NOT NULL UNIQUE,
    last_close   NUMERIC(18,4),
    current_price NUMERIC(18,4),
    high_52w     NUMERIC(18,4),
    low_52w      NUMERIC(18,4),
    fetched_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY — anon key = READ ONLY
-- Writes go through service key (fetcher on Mac only)
-- ══════════════════════════════════════════════════════════════

ALTER TABLE equity_india_prices       ENABLE ROW LEVEL SECURITY;
ALTER TABLE equity_international_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE mf_navs                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE forex_rates               ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_history         ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_prices          ENABLE ROW LEVEL SECURITY;

-- Allow anon (Streamlit) to SELECT only
CREATE POLICY "anon_read_equity_india"
    ON equity_india_prices FOR SELECT USING (true);

CREATE POLICY "anon_read_equity_intl"
    ON equity_international_prices FOR SELECT USING (true);

CREATE POLICY "anon_read_mf_navs"
    ON mf_navs FOR SELECT USING (true);

CREATE POLICY "anon_read_forex"
    ON forex_rates FOR SELECT USING (true);

CREATE POLICY "anon_read_history"
    ON portfolio_history FOR SELECT USING (true);

CREATE POLICY "anon_read_watchlist"
    ON watchlist_prices FOR SELECT USING (true);
