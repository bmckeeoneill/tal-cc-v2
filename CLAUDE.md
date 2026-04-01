# CLAUDE.md — TAL Command Center

## Project Overview

TAL Command Center (TCC) is a Streamlit sales intelligence tool built for Brian O'Neill, Oracle NetSuite AE. It ingests Gmail signals, processes them against a 297-account territory list, and surfaces outreach opportunities.

**Stack:** Python · Streamlit · Supabase (Postgres + Storage) · Claude API · psycopg2 · Gmail API

**Working directory:** `/Users/brianoneill/Desktop/TAL_CC_clean`
**App runs on:** `http://localhost:8501`
**Venv:** `venv/` inside the project directory
**Restart command:** `lsof -ti :8501 | xargs kill -9 && cd /Users/brianoneill/Desktop/TAL_CC_clean && source venv/bin/activate && streamlit run app.py --server.port 8501`

---

## Architecture

### Entry Point
- `app.py` — Streamlit shell: routing, horizontal chat bar, page dispatch
- Pages live in `pages/_*.py` (underscore prefix, not Streamlit auto-pages)
- Routing via `st.session_state.page`, helper `go()` in `pages/_shared.py`

### Key Files
| File | Purpose |
|------|---------|
| `app.py` | Shell, routing, chat bar |
| `db.py` | All Supabase queries |
| `config.py` | Centralized constants (REP_ID, MODEL, MATCH_THRESHOLD, get_anthropic_key) |
| `gmail_ingest.py` | Gmail API polling, raw signal storage |
| `signal_processor.py` | Two-pass classification + account matching |
| `run_pipeline.py` | Orchestrates ingest → process → match |
| `load_tal.py` | CSV → Supabase upsert for TAL accounts |
| `pages/_dashboard.py` | Home tile grid |
| `pages/_tal.py` | Account list with search/filter |
| `pages/_account_detail.py` | Single account view |
| `pages/_activity.py` | Signal feed |
| `pages/_misc.py` | TAL Changes, Best Targets, Claimed Awaiting Briefing |
| `pages/_events.py` | Events list |
| `pages/_leads.py` | Leads tile |
| `pages/_unmatched.py` | Review queue |
| `pages/_shared.py` | Shared helpers (go, page nav) |
| `mock_data.py` | Mock data for Best Targets tile (Phase 7 replacement) |

### Cron Jobs (macOS crontab)
- **Gmail ingest:** every 5 min M-F 8am–6pm PT · every 15 min off-hours
- **Pipeline:** every 5 min M-F 8am–6pm PT only
- TZ=America/Los_Angeles set in crontab

---

## Core Rules

### AI Output
- **No AI on page load.** Every Claude call must be triggered by a user button click. No Claude calls fire automatically when a page renders.
- Log prompt, model version, and timestamp alongside all AI output in Supabase.
- Outreach tone: 3-part structure (industry hook + signal reference + cheeky CTA). No em dashes. Short sentences. Human voice.

### Data Integrity
- `signals_raw` is an append-only audit log. Never modify or delete rows after ingest.
- If match confidence < 80%, write to `signal_review_queue` with reason. Never auto-tag low-confidence matches.
- Every table has a `rep_id` column. No exceptions — this makes the system portable to other reps.

### Signal Processing
- Two-pass classification: signal type first, then account tagging or global fanout.
- Global/webinar events fan out to all relevant accounts — never dropped because no single account matched.
- In-person events matched by region/state.
- Fuzzy match threshold: 80%. Below → review queue.

### TAL Lifecycle
- `accounts.active` — false means the account dropped off the TAL. Invisible everywhere in normal app flow.
- `accounts.assigned` — false means Brian hasn't acknowledged a new account yet (shows in TAL Changes).
- When refreshing the TAL: run `load_tal.py` with the new CSV. It upserts active accounts, marks dropped accounts inactive, and flags net-new accounts as unassigned.
- All `db.py` account queries filter `active = true` by default.

### Email Ingest
- Gmail API polling (not Postmark, not Zapier).
- Raw payload goes to `signals_raw` intact — no processing in the receiver.
- ALLOWED_SENDERS whitelist in `gmail_ingest.py`. Brian's addresses are always included.
- Attachment filenames: replace spaces with underscores before Supabase Storage upload.

### Schema
- `street`, `city`, `state`, `zip` exist on `accounts` table — populated by `load_tal.py`.
- `tech_stack` is a Postgres array field on `accounts`.
- `sdr_name`, `sdr_assigned_at`, `briefing_sent_at` on `accounts` for SDR workflow.

---

## Chat Context

- `get_tal_summary_context()` — used on non-account pages. Pulls full territory: all 297 accounts with every signal, note, flagged event, SDR status, and address. Bulk queries, no N+1.
- `get_account_chat_context()` — used on account detail page. Full deep block for the focused account + lightweight one-liner for every other territory account.
- Chat input placeholder: "Ask your TAL assistant anything"

---

## What's Deferred (Phase 7)

- Best Targets tile: still uses `mock_data.MOCK_TARGETS` — replace with real scoring
- Weekly analysis and digest scoring (`run_weekly_analysis`, `run_weekly_digest`) — removed from pipeline, not useful until more signal volume
- Outreach hook library per vertical (with Brian's field stories)
- Event vertical matching (Claude-based — currently fans out to all accounts for webinars)
- Pipeline Scout tile, Quick Links bar
- Streamlit Cloud deployment (needs Gmail refresh token extracted to secrets)
