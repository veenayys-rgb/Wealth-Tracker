# WEALTH TRACKER v2 — COMPLETE BLUEPRINT
**Date:** May 2026  
**Storage:** iCloud Drive + Supabase  
**Frontend:** Streamlit (Community Cloud → Tailscale later)

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR MAC                                  │
│                                                                  │
│  watcher.py ──► fetcher/run.py                                  │
│                     ├── equity.py      (NSE/BSE/ADX/US)         │
│                     ├── mutual_funds.py (AMFI NAVs + ETFs)      │
│                     └── forex.py       (AED/INR, USD/INR)       │
│                           │                                      │
│              ┌────────────┴────────────┐                        │
│              ▼                         ▼                         │
│    iCloud Drive/WealthTracker/    Supabase DB                   │
│    config/ (static holdings)      (live prices & history)       │
└─────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                              Streamlit Community Cloud
                                  (Web App / iPhone)
```

---

## DATA SOURCES

| Asset Class         | Source          | Method                        |
|---------------------|-----------------|-------------------------------|
| India Equity        | yfinance        | Batch `.NS` → `.BO` fallback  |
| ADX Stocks (UAE)    | yfinance        | Batch `.AD` suffix            |
| US Stocks           | yfinance        | Batch (no suffix)             |
| Indian ETFs         | AMFI            | ISIN lookup (in MF sheet)     |
| MF NAVs             | AMFI            | ISIN lookup                   |
| Forex (AED/USD→INR) | yfinance        | `AEDINR=X`, `USDINR=X`       |

---

## ICLOUD CONFIG FILES (Static — you edit when buying/selling)

```
~/iCloud Drive/WealthTracker/config/
├── equity_india.json
├── equity_international.json
├── mutual_funds_vinay.json       ← includes ETFs
├── mutual_funds_harsh.json       ← includes ETFs
├── watchlist.json
├── bank_accounts.json
├── fixed_deposits.json
└── insurance.json
```

## SUPABASE TABLES (Dynamic — fetcher writes, Streamlit reads)

```
equity_india_prices
equity_international_prices
mf_navs                           ← includes ETF NAVs
forex_rates
portfolio_history
watchlist_prices
```

---

## PAGE 1: PORTFOLIO (Asset Allocation by Individual)

> Renamed from existing "Dashboard"
> Shows 4 asset allocation tables — Vinay | Harsh | Anusha | Combined

```
╔══════════════════════════════════════════════════════════════════╗
║  PORTFOLIO                         Last refreshed: 13-May-2026  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ┌────────────────────────────┐  ┌────────────────────────────┐ ║
║  │ ASSET ALLOCATION — VINAY  │  │ ASSET ALLOCATION — HARSH   │ ║
║  │ Asset Class  |Inv|CV|G/L|%│  │ Asset Class  |Inv|CV|G/L|% │ ║
║  │ Equities–NSE |   |  |   | │  │ Equities–NSE |   |  |   |  │ ║
║  │ Mutual Funds |   |  |   | │  │ Mutual Funds |   |  |   |  │ ║
║  │ Bank Accounts|   |  |   | │  │ Bank Accounts|   |  |   |  │ ║
║  │ Fixed Deps   |   |  |   | │  │ Fixed Deps   |   |  |   |  │ ║
║  │ Bank UAE     |   |  |   | │  │ Bank UAE     |   |  |   |  │ ║
║  │ Insurance    |   |  |   | │  │ Insurance    |   |  |   |  │ ║
║  │ ────────────────────────  │  │ ────────────────────────── │ ║
║  │ TOTAL        |   |  |   | │  │ TOTAL        |   |  |   |  │ ║
║  └────────────────────────────┘  └────────────────────────────┘ ║
║                                                                  ║
║  ┌────────────────────────────┐  ┌────────────────────────────┐ ║
║  │ ASSET ALLOCATION — ANUSHA │  │ ASSET ALLOCATION — COMBINED│ ║
║  │ Asset Class  |Inv|CV|G/L|%│  │ Asset Class  |Inv|CV|G/L|% │ ║
║  │ Equities–NSE |   |  |   | │  │ Equities–NSE |   |  |   |  │ ║
║  │ Mutual Funds |   |  |   | │  │ Mutual Funds |   |  |   |  │ ║
║  │ Bank Accounts|   |  |   | │  │ Bank Accounts|   |  |   |  │ ║
║  │ Fixed Deps   |   |  |   | │  │ Fixed Deps   |   |  |   |  │ ║
║  │ Bank UAE     |   |  |   | │  │ Bank UAE     |   |  |   |  │ ║
║  │ Insurance    |   |  |   | │  │ Insurance    |   |  |   |  │ ║
║  │ ────────────────────────  │  │ ────────────────────────── │ ║
║  │ TOTAL        |   |  |   | │  │ TOTAL        |   |  |   |  │ ║
║  └────────────────────────────┘  └────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════════╝

Columns per table: Asset Class | Invested (₹) | Current Value (₹) | Gain/Loss (₹) | Allocation %
Note: Insurance uses Surrender Value. Bank/FD/UAE balances in INR equivalent.
```

---

## PAGE 2: INDIA EQUITY

> NOTE: Indian ETFs are listed in the Mutual Funds sheet, NOT here.
> No Exchange column — all fetched NSE first, BSE fallback (internal only).

```
╔══════════════════════════════════════════════════════════════════╗
║  INDIA EQUITY — VINAY          Last fetched: 13-May-2026 15:32  ║
╠══════╦═══════════════╦════════╦══════════╦════════╦════════════╣
║ ISIN ║ Company Name  ║ Symbol ║Hold. Type║ Source ║  Buy Date  ║
╠══════╬═══════════════╬════════╬══════════╬════════╬════════════╣
║      ║               ║        ║          ║        ║            ║
╠══════╩═══════════════╩════════╩══════════╩════════╩════════════╣

Continued columns →

╦═════╦══════════╦═══════════╦══════════════╦═════════════╦══════════╦══════════╦══════════╗
║ Qty ║ Avg Cost ║ Invested  ║ Curr Price   ║ Curr Value  ║Gain/Loss ║Return %  ║% of Port.║
╬═════╬══════════╬═══════════╬══════════════╬═════════════╬══════════╬══════════╬══════════╣
║     ║    ₹     ║    ₹      ║      ₹       ║     ₹       ║ ▲/▼ ₹   ║ ▲/▼ %   ║   X.X%   ║
╩═════╩══════════╩═══════════╩══════════════╩═════════════╩══════════╩══════════╩══════════╝

Full column order:
ISIN | Company Name | Symbol | Holding Type | Source | Buy Date |
Qty | Avg Cost (₹) | Invested (₹) | Current Price (₹) | Current Value (₹) |
Gain/Loss (₹) | Return (%) | % of Portfolio
```

> **Holding Type values**: NRE | NRO
> **Source values**: Market | IPO | DAD

---

## PAGE 3: MUTUAL FUNDS — VINAY
## PAGE 4: MUTUAL FUNDS — HARSH
## PAGE 5: MUTUAL FUNDS — ANUSHA (structure ready, empty for now)

> Separate pages for Vinay and Harsh (identical structure)
> Includes Indian ETFs — no distinction from regular MFs
> NAV Date shown in page header

```
╔══════════════════════════════════════════════════════════════════╗
║  MUTUAL FUNDS — VINAY          NAV Date: 13-May-2026            ║
╠══════════╦══════╦═══════════════════╦════════════════════════╣
║ Folio No ║ ISIN ║ Fund Name         ║ Fund Name (AMFI)       ║
╠══════════╬══════╬═══════════════════╬════════════════════════╣
║          ║      ║                   ║                        ║
╠══════════╩══════╩═══════════════════╩════════════════════════╣

Continued columns →

╦═══════╦══════════╦═══════════╦══════════════╦═════════════╦══════════╦══════════╦══════════╗
║ Units ║ Avg NAV  ║ Invested  ║ Current NAV  ║ Curr Value  ║Gain/Loss ║ Return % ║% of Port.║
║ Held  ║   (₹)   ║   (₹)    ║    (₹)       ║    (₹)      ║   (₹)   ║          ║          ║
╬═══════╬══════════╬═══════════╬══════════════╬═════════════╬══════════╬══════════╬══════════╣
║       ║          ║           ║              ║             ║  ▲/▼     ║  ▲/▼ %   ║   X.X%   ║
╩═══════╩══════════╩═══════════╩══════════════╩═════════════╩══════════╩══════════╩══════════╝

Full column order:
Folio No | ISIN No | Fund Name | Fund Name (AMFI) |
Units Held | Avg NAV (₹) | Invested (₹) |
Current NAV (₹) | Current Value (₹) | Gain/Loss (₹) | Return % | % of Portfolio
```

---

## PAGE 4: INTERNATIONAL

> UAE (ADX) + US stocks + any future region
> Currency column + INR equivalent auto-calculated from fetched forex

```
╔══════════════════════════════════════════════════════════════════╗
║  INTERNATIONAL EQUITY          Last fetched: 13-May-2026 15:32  ║
║                                AED/INR: 22.89 | USD/INR: 84.12  ║
╠══════════════╦════════╦══════╦════════╦══════╦═════════════════╣
║ Name         ║ Symbol ║ ISIN ║ Region ║ Exch ║ Currency        ║
╠══════════════╬════════╬══════╬════════╬══════╬═════════════════╣
║ ADNOC Dist.  ║ADNOCDIST║     ║  UAE   ║ ADX  ║ AED             ║
║ Apple Inc.   ║ AAPL   ║      ║  US    ║ NYSE ║ USD             ║
╠══════════════╩════════╩══════╩════════╩══════╩═════════════════╣

Continued columns →

╦═════╦══════════╦═══════════╦════════════╦═══════╦════════════╦══════════════╗
║ Qty ║Avg Cost  ║Curr Price ║Curr Value  ║ Forex ║Curr Value  ║ Gain/Loss    ║
║     ║  (FCY)   ║  (FCY)    ║  (FCY)     ║ Rate  ║  (INR)     ║  (INR)       ║
╬═════╬══════════╬═══════════╬════════════╬═══════╬════════════╬══════════════╣
║     ║          ║           ║            ║ 22.89 ║            ║  ▲/▼         ║
╩═════╩══════════╩═══════════╩════════════╩═══════╩════════════╩══════════════╝

Full column order:
Name | Symbol | ISIN | Region | Exchange | Currency | Source (Market/IPO/DAD) | Buy Date |
Qty | Avg Cost (FCY) | Invested (FCY) | Current Price (FCY) | Current Value (FCY) |
Forex Rate | Current Value (INR) | Gain/Loss (INR) | Return (%) | % of Portfolio
```

---

## PAGE 5: WATCHLIST

> 52-week high/low. Not holdings — just stocks to monitor.

```
╔══════════════════════════════════════════════════════════════════╗
║  WATCHLIST                     Last fetched: 13-May-2026 15:32  ║
╠══════════════╦════════╦══════╦════════╦══════════╦═════════════╣
║ Name         ║ Symbol ║ ISIN ║ Region ║Last Close║ Curr Price  ║
╠══════════════╬════════╬══════╬════════╬══════════╬═════════════╣
║              ║        ║      ║ NSE/   ║          ║             ║
║              ║        ║      ║ ADX/US ║          ║             ║
╠══════════════╩════════╩══════╩════════╩══════════╩═════════════╣

Continued columns →

╦══════════╦══════════╦══════════════╦══════════════╗
║ 52W High ║ 52W Low  ║ % from High  ║ % from Low   ║
╬══════════╬══════════╬══════════════╬══════════════╣
║          ║          ║  ▼ -XX%      ║  ▲ +XX%      ║
╩══════════╩══════════╩══════════════╩══════════════╝

Full column order:
ISIN Number | Symbol | Company Name | Region (NSE/ADX/US) | Currency |
Last Close Price | Current Price | 52W High | 52W Low | % from 52W High | % from 52W Low
```

---

## PAGE 6: PORTFOLIO HISTORY

> Market-aware: records snapshot when NSE is closed.
> Updated end-of-day (after 3:30 PM IST) or on closed market days.

```
╔══════════════════════════════════════════════════════════════════╗
║  PORTFOLIO HISTORY                                               ║
╠══════════════╦════════════╦════════════╦══════════╦════════════╣
║ Date         ║ Eq Invested║ Eq Value   ║MF Invest ║ MF Value   ║
╠══════════════╬════════════╬════════════╬══════════╬════════════╣
║ 13-May-2026  ║            ║            ║          ║            ║
║ 12-May-2026  ║            ║            ║          ║            ║
╠══════════════╩════════════╩════════════╩══════════╩════════════╣

Continued columns →

╦════════════╦════════════╦══════════════╦════════════╦══════════╗
║Intl Invested║ Intl Value ║ Total Invested║ Total CV   ║Gain/Loss ║
╬════════════╬════════════╬══════════════╬════════════╬══════════╣
║            ║            ║              ║            ║ ▲/▼      ║
╩════════════╩════════════╩══════════════╩════════════╩══════════╝

Full column order:
Date | Shares Invested | Shares CV | MF Invested - Vinay | MF CV - Vinay |
MF Invested - Harsh | MF CV - Harsh | Total Invested | Total CV | Gain/Loss | Return %
```

---

## PAGE 7: BANK ACCOUNTS — INDIA
## PAGE 8: BANK ACCOUNTS — UAE

> Two separate pages. Manually updated via Streamlit UI.
> UAE balance INR equivalent auto-calculated from fetched AED/INR rate.

**India Bank Sheet:**
```
╔══════════════════════════════════════════════════════════════════╗
║  BANK ACCOUNTS — INDIA                                           ║
╠══════════╦════════════╦══════════════════╦══════╦═══════╦══════╣
║Bank Name ║ Acct Type  ║ Account No.(last4)║ IFSC ║ Owner ║2nd   ║
╠══════════╬════════════╬══════════════════╬══════╬═══════╬══════╣
║          ║ NRE/NRO/   ║ XXXX             ║      ║       ║      ║
║          ║ Savings/   ║                  ║      ║       ║      ║
╠══════════╩════════════╩══════════════════╩══════╩═══════╩══════╣

Continued columns →

╦═══════════════════╗
║ Current Balance(₹)║
╬═══════════════════╣
║                   ║
╩═══════════════════╝

Full column order:
Bank Name | Account Type | Account No. (last 4) | IFSC |
Owner | 2nd Account Holder | Current Balance (₹)
```

**UAE Bank Sheet:**
```
╔══════════════════════════════════════════════════════════════════╗
║  BANK ACCOUNTS — UAE                                             ║
╠══════════╦══════════╦════════════╦════════════╦═══════╦════════╣
║Bank Name ║ Currency ║ Acct Type  ║ Account No.║ Owner ║Bal(AED)║
╠══════════╬══════════╬════════════╬════════════╬═══════╬════════╣
║          ║ AED      ║            ║            ║       ║        ║
╠══════════╩══════════╩════════════╩════════════╩═══════╩════════╣

Continued columns →

╦════════════╗
║ Equiv. INR ║
╬════════════╣
║ (auto)     ║
╩════════════╝

Full column order:
Bank Name | Currency | Account Type | Account No. |
Owner | Current Balance (AED) | Equiv. INR (auto-calculated)
```

---

## PAGE 8: FIXED DEPOSITS

> Static data. Both India + UAE. Manually maintained.

```
╔══════════════════════════════════════════════════════════════════╗
║  FIXED DEPOSITS                                                  ║
╠══════════╦═════════╦══════════╦═══════════╦═════════╦══════════╣
║ Bank     ║ Country ║ Currency ║ Principal ║Rate (%) ║Start Date║
╠══════════╬═════════╬══════════╬═══════════╬═════════╬══════════╣
║          ║ India   ║ INR      ║           ║         ║          ║
║          ║ UAE     ║ AED      ║           ║         ║          ║
╠══════════╩═════════╩══════════╩═══════════╩═════════╩══════════╣

Continued columns →

╦══════════════╦════════════════╦══════════════╦════════╗
║ Maturity Date║ Maturity Amount║ Tenure       ║ Edit   ║
╬══════════════╬════════════════╬══════════════╬════════╣
║              ║                ║ XX months    ║  ✏️    ║
╩══════════════╩════════════════╩══════════════╩════════╝

Full column order:
Bank | FD No | Owner | Currency | Amount | Equiv INR |
Rate % p.a. | Start Date | Maturity Date | Maturity Amount (₹) | Maturity Equiv INR
```

---

## PAGE 9: INSURANCE

> Static data. All types (Term / Endowment / ULIP / Health). Manually maintained.
> Upcoming premium due dates highlighted.

```
╔══════════════════════════════════════════════════════════════════╗
║  INSURANCE                  ⚠️ 2 premiums due within 30 days    ║
╠══════════════╦══════════╦══════════╦════════╦═══════════════════╣
║ Company Name ║Ins. Type ║Policy No ║ Owner  ║ Beneficiary       ║
╠══════════════╬══════════╬══════════╬════════╬═══════════════════╣
║              ║ Term     ║          ║ Vinay  ║                   ║
║              ║ ULIP     ║          ║ Harsh  ║                   ║
║              ║ Health   ║          ║ Vinay  ║                   ║
╠══════════════╩══════════╩══════════╩════════╩═══════════════════╣

Continued columns →

╦══════════╦═══════════════╦════════════════╦══════════════╦══════════════════╗
║ Currency ║ Insured Value ║ Surrender Value║Prem. Amount  ║ Prem. Pay Term   ║
╬══════════╬═══════════════╬════════════════╬══════════════╬══════════════════╣
║ INR      ║               ║                ║              ║ 20 years         ║
╩══════════╩═══════════════╩════════════════╩══════════════╩══════════════════╝

Continued columns →

╦═════════════╦══════════════╦══════════════════╦═══════════════╗
║ Yrs Paid    ║ Prem Paid YTD║ Next Premium Due  ║ Maturity Date ║
╬═════════════╬══════════════╬══════════════════╬═══════════════╣
║             ║              ║ ⚠️ 20-May-2026   ║               ║
╩═════════════╩══════════════╩══════════════════╩═══════════════╝

Full column order:
Company Name | Insurance Type | Policy No | Owner | Beneficiary | Currency |
Insured Value | Surrender Value | Premium Amount | Premium Payment Term |
Years Premium Paid | Premium Paid YTD | Next Premium Due | Maturity Date
```

---

## PAGE 10: DASHBOARD (Main Home Page)

> The primary landing page. Shows full net worth by aggregating all sheets.
> Summary totals + charts. Design of charts to be finalised separately.

```
╔══════════════════════════════════════════════════════════════════╗
║  DASHBOARD — WEALTH TRACKER        Last refreshed: 13-May-2026  ║
║                                    AED/INR: 22.89 | USD/INR: 84 ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          ║
║  │ Total Net    │  │ Total        │  │ Total        │          ║
║  │ Worth        │  │ Invested     │  │ Gain / Loss  │          ║
║  │ ₹X,XX,XX,XXX │  │ ₹X,XX,XX,XXX │  │ ▲ ₹XX,XX,XXX │          ║
║  └──────────────┘  └──────────────┘  └──────────────┘          ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  NET WORTH BREAKDOWN                                             ║
║                                                                  ║
║  Asset Class        Invested (₹)  Current (₹)  Gain/Loss  Return║
║  ────────────────────────────────────────────────────────────    ║
║  India Equity       XX,XX,XXX     XX,XX,XXX     ▲X,XX,XXX  X.X% ║
║  MF — Vinay         XX,XX,XXX     XX,XX,XXX     ▲X,XX,XXX  X.X% ║
║  MF — Harsh         XX,XX,XXX     XX,XX,XXX     ▲X,XX,XXX  X.X% ║
║  International      XX,XX,XXX     XX,XX,XXX     ▲X,XX,XXX  X.X% ║
║  Bank — India       —             XX,XX,XXX     —           —    ║
║  Bank — UAE         —             XX,XX,XXX     —           —    ║
║  Fixed Deposits     —             XX,XX,XXX     —           —    ║
║  Insurance          —             XX,XX,XXX     —           —    ║
║  ────────────────────────────────────────────────────────────    ║
║  TOTAL NET WORTH    XX,XX,XXX     XX,XX,XXX     ▲X,XX,XXX  X.X% ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  [Charts and graphs — layout to be finalised separately]        ║
║   • Asset allocation pie chart                                   ║
║   • Net worth trend (from Portfolio History)                     ║
║   • Gain/Loss by asset class                                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Note: Insurance uses Surrender Value. Bank/FD in INR equivalent.
```

---

## PROJECT FILE STRUCTURE

```
~/iCloud Drive/WealthTracker/
│
├── config/                          ← STATIC — edit when buying/selling
│   ├── equity_india.json
│   ├── equity_international.json
│   ├── mutual_funds_vinay.json      ← includes ETFs
│   ├── mutual_funds_harsh.json      ← includes ETFs
│   ├── watchlist.json
│   ├── bank_accounts.json
│   ├── fixed_deposits.json
│   └── insurance.json
│
├── fetcher/                         ← RUNS ON YOUR MAC
│   ├── equity.py                    ← NSE/BSE/ADX/US batch yfinance
│   ├── mutual_funds.py              ← AMFI NAVs + ETFs
│   ├── forex.py                     ← AED/INR, USD/INR
│   └── run.py                       ← orchestrator
│
├── app/                             ← STREAMLIT APP (deployed to cloud)
│   ├── Home.py                      ← entry point
│   └── pages/
│       ├── 1_Portfolio.py
│       ├── 2_India_Equity.py
│       ├── 3_Mutual_Funds.py        ← tabs: Vinay | Harsh (incl. ETFs)
│       ├── 4_International.py
│       ├── 5_Watchlist.py
│       ├── 6_Portfolio_History.py
│       ├── 7_Bank_Accounts.py
│       ├── 8_Fixed_Deposits.py
│       ├── 9_Insurance.py
│       └── 10_Dashboard.py
│
├── watcher.py                       ← watches for trigger, runs fetcher
├── requirements.txt
└── .streamlit/
    └── secrets.toml                 ← Supabase credentials (NOT on GitHub)
```

---

## KEY RULES

1. Indian ETFs (CPSEETF, GOLDCASE etc.) → priced via AMFI → appear in **Mutual Funds** sheet only
2. Insurance net worth contribution → **Surrender Value** (not insured value)
3. Bank balances → **manual update** via Streamlit UI
4. FDs + Insurance → **static data**, manually maintained
5. Portfolio History → records only when **NSE market is closed** (3:30 PM IST cutoff)
6. International values → shown in **both FCY and INR equivalent**
7. Existing files → **never touched** — full rebuild in new iCloud location

---

## SUPABASE DETAILS

- Project ID: bopqwksvunejedhgdvxv
- URL: https://bopqwksvunejedhgdvxv.supabase.co
- Security: Row Level Security enabled — anon key = read only, writes via service key on Mac only
