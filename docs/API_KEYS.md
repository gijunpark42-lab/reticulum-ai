# API keys and free data sources for the map

Where each key goes: **`C:\Users\calif\Desktop\earnings-ai\.env`** (one `NAME=value` per line, no quotes).
`config`/scripts read them with `python-dotenv`. Never commit `.env` (it is gitignored). Never paste keys into
chat, docs, or code. The trading bot keeps its own copy at `C:\Users\calif\Desktop\Trading\.env`; keys marked
"same key" can be copied between the two files.

## Already in `.env`

| Key | Used by | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | legacy `main.py` API functions (enrichment now runs inside Claude Code, so this is rarely used) | |
| `DART_API_KEY` | `dart.py` (Korean filings) | https://opendart.fss.or.kr/ |
| `ALPHAVANTAGE_API_KEY` | `av.py` transcripts + `EARNINGS_CALL_TRANSCRIPT` | free 25 requests/day; same key as the bot |

## Add these (all free, all company-primary sources — no news feeds)

| Key | Sign up | Free limit | What it unlocks for the map |
|---|---|---|---|
| `EDGAR_USER_AGENT` | no account. SEC only requires a User-Agent with a contact e-mail, e.g. `earnings-ai research your@email` — https://www.sec.gov/os/accessing-edgar-data | 10 requests/s | 8-K (guidance updates, material agreements Item 1.01, earnings releases Item 2.02), 10-K customer-concentration paragraphs, 10-Q segment revenue, XBRL facts. Full-text search: `https://efts.sec.gov/LATEST/search-index?q=...&forms=8-K` |
| (library, no key) **edgartools** | `pip install edgartools` — https://github.com/dgunning/edgartools (MIT) | none | Python access to the above: `Company("NVDA").get_filings(form="10-K")`, section text, XBRL incl. segment dimensions. Reads `EDGAR_USER_AGENT` via `set_identity()` |
| `FINNHUB_API_KEY` | https://finnhub.io/register | 60 calls/min, personal use | earnings calendar with estimates (`/calendar/earnings`), earnings surprises (`/stock/earnings`), company news (the bot uses this; the map should not) — same key as the bot |
| `FRED_API_KEY` | https://fred.stlouisfed.org/docs/api/api_key.html (free FRED account) | 120 req/min | macro series (rates, CPI, NFCI) — used by the bot's macro agent; same key as the bot |
| `API_NINJAS_KEY` (optional) | https://api-ninjas.com/register | free tier, non-commercial, premium fields locked | backup transcript source `https://api.api-ninjas.com/v1/earningscalltranscript?ticker=NVDA&year=2026&quarter=2` |
| `POLYGON_API_KEY` (optional) | https://polygon.io/dashboard/signup | 5 calls/min, end-of-day | backup price/reference data — same key as the bot |

Not worth it: Finnhub transcripts (premium only), Seeking Alpha (paid), Apify scrapers (licence unclear), Glassnode (paid).

## How the map should use them (keeps the "company said it" rule)

1. **8-K** — for every mapped US ticker, pull 8-Ks since the last enrichment; Items 1.01 / 2.02 / 7.01 / 8.01 carry
   contracts, guidance changes and investor-day decks. Save the text under `transcripts/edgar/<ticker>_8k_<date>.txt`
   and enrich like a transcript (source label `NVIDIA 8-K (09-10-2026)`).
2. **10-K customer concentration** — Item 1 / Item 7 / notes ("customers accounting for more than 10% of revenue").
   These are hard, dated edges with percentages: `connects_to[].contracts[]` entries with `type: "10-K customer concentration"`.
3. **10-Q segment revenue** — data-center / AI segment share and growth as dated `quarterly_data` figures.
4. **Curated metrics as numbers** — in `company_metrics.json` add numeric fields next to the text
   (`backlog_usd`, `guide_low_usd`, `guide_high_usd`, `capex_usd`, `asof`) so downstream code can compute
   quarter-over-quarter deltas instead of keyword-matching sentences.

## Example `.env` block to append

```
EDGAR_USER_AGENT=earnings-ai research gijunpark42@gmail.com
FINNHUB_API_KEY=
FRED_API_KEY=
API_NINJAS_KEY=
POLYGON_API_KEY=
```
