-- Card Dues table (summary of UAE credit card statements, pushed from the local Card Extractor)
-- Run this once in the Supabase SQL Editor
--
-- RLS is on with NO anon policy: only the service key (Streamlit app via utils.db, and the
-- local Card Extractor) can read or write. The public anon key cannot see these rows.

CREATE TABLE IF NOT EXISTS card_dues (
    id              text primary key,          -- "<BANK>_<statement_date>", e.g. "FAB_2026-09-11"
    bank            text        not null,
    statement_date  date        not null,
    due_date        date,
    total_due       numeric,
    paid_auto       boolean     not null default false,  -- payment seen on the next statement
    next_stmt_in    boolean     not null default false,  -- next statement loaded (payment status known)
    marked_paid     boolean     not null default false,  -- ticked "Mark paid" (phone or Mac)
    updated_at      timestamptz not null default now()
);

ALTER TABLE card_dues ENABLE ROW LEVEL SECURITY;
