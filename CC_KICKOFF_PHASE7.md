# TCC Phase 7 — Scoring, Contacts, Similar Customers + Polish
## Claude Code Kickoff Document

---

## Context

TCC is live on Streamlit Cloud (`bmckeeoneill/tal-cc-v2`) and running locally on Brian's Mac. The Mac handles Gmail ingest and signal processing via cron. SLC is a read/write frontend on the same Supabase DB. Password protected.

Working directory: `/Users/brianoneill/Desktop/TAL_CC_clean`
Python: 3.14, venv at `venv/`
AI model: `claude-sonnet-4-6`
Restart command: `lsof -ti :8501 | xargs kill -9 && cd /Users/brianoneill/Desktop/TAL_CC_clean && source venv/bin/activate && streamlit run app.py --server.port 8501`

---

## What Phase 6 / 6.5 Built

- Split app.py into page modules under `pages/_*.py`
- Streamlit Cloud deployment with secrets, password gate
- Similar Customers: NAICS-based AI matching, lock/dismiss, keyword search
- Contacts: extraction from forwarded emails, review queue, paste ingester with Claude parsing
- Briefing: lead highlight, battle card attachment, Who to Call section (from confirmed contacts)
- Top Targets tile: now shows real starred accounts in TAL list view
- Content library and resource matching for briefings
- NAICS enrichment on accounts
- One pager / battle card generation

---

## Phase 7 Build List

### 1. Best Targets — Real Scoring (replaces mock data)

Currently `pages/_misc.py` `render_targets()` shows starred accounts only. The dashboard tile still pulls from `mock_data.MOCK_TARGETS`.

Replace mock data with a real scoring model:
- Score = weighted sum of: signal recency, signal count, has lead highlight, has contacts, has locked similar customers, starred flag
- Store score on `accounts.score` (column already exists)
- Run scoring on pipeline tick or on-demand button
- Best Targets tile on dashboard shows top 5 by score with mini signal summary

### 2. Manual Similar Customer Entry

User should be able to paste a NetSuite URL or company website on the account detail page and add it as a pinned similar customer.

- Text field below keyword search in Similar Customers expander
- On submit: try to scrape page `<title>` for company name (works for regular sites, fails gracefully for NetSuite auth walls)
- If scrape fails: show editable name field for manual entry
- On confirm: find or create customer in `customers` table, lock to account
- Add `favorited` boolean to `customers` table — star toggle on all customer rows, favorited customers surface first in searches

### 3. Customer Favorites Toggle

- Migration: add `favorited boolean default false` to `customers` table
- Star toggle on locked customer rows and search result rows
- `db.toggle_customer_favorited(customer_id, favorited)`
- Favorited customers always sort first in similar customer results

### 4. ZoomInfo Deep Link (if solvable)

`accounts.zi_id` is populated from the TAL CSV. The challenge is constructing an authenticated deep link.
- Current attempts: `www.zoominfo.com/c/-/{id}` and `app.zoominfo.com/#/apps/profile/company/{id}/overview` both fail to carry the browser session
- Option: store the full ZoomInfo URL in the TAL CSV export and load it into a new `zoominfo_url` column
- If Brian can export ZoomInfo URLs from his TAL CSV, add `zoominfo_url` to `load_tal.py` and display on account record + briefing

### 5. Outreach Hook Library

Brian has field stories and vertical-specific hooks that make outreach feel genuine.
- `content_library.json` already exists — extend with outreach hooks per vertical
- Surface 1-2 relevant hooks when generating outreach draft on account detail page
- Hooks tagged by industry/NAICS, matched to account before generation

### 6. Event Vertical Matching

Currently all webinar/global events fan out to every account (no filtering by relevance).
- Add Claude-based relevance scoring: does this event topic match this account's industry/NAICS?
- Only fan out to accounts where relevance score > threshold
- Reduces noise in account signal feeds

---

## Carry-Forward Rules

- No AI on page load. Every Claude call triggered by button.
- Log all AI calls to Supabase with prompt, model, timestamp.
- Every table has `rep_id`. No exceptions.
- `signals_raw` is append-only.
- All `db.py` account queries filter `active = true`.
- Outreach tone: 3-part structure, no em dashes, short sentences, human voice.
- Push to git at end of every session.
