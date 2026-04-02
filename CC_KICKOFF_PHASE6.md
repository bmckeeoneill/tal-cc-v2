# TCC Phase 6 — Cleanup, Deployment + New Features
## Claude Code Kickoff Document

---

## Context

Continuing from Phase 5. TCC is running on port 8501 with 296 accounts, Gmail ingest live, full signal pipeline built, events ingestion working, and content generation section on account pages.

Working directory: `/Users/brianoneill/Desktop/TAL_CC_clean`
Python: 3.14, venv at `venv/`
AI model: `claude-sonnet-4-6`

---

## What Phase 6 Builds

1. Codebase review and cleanup
2. Split app.py into page files
3. GitHub setup
4. Tech stack field on account pages
5. Generate Invite button per event
6. Flag event for briefing button
7. Leads tile
8. SDR field + Claimed Awaiting Briefing tile
9. Streamlit Cloud deployment

---

## Build Order and Specs

### Step 1: Codebase Review and Cleanup

Before building anything new, review the entire codebase for quality issues:

- Identify and remove duplicated logic
- Consolidate any db.py functions that do the same thing in slightly different ways
- Make sure every Claude API call goes through a single shared function rather than being scattered across files
- Add basic error handling anywhere it's missing - especially around Supabase queries and Claude calls
- Flag anything that would be risky to extend in Phase 6

Report what was found and what was cleaned up before moving to Step 2.

---

### Step 2: Split app.py into Page Files

`app.py` should not be a single monolithic file. Split it into separate files by page:

- `app.py` — entry point only: imports, session state init, page router, and chat bar
- `pages/dashboard.py` — main dashboard with tiles
- `pages/account_detail.py` — account detail page
- `pages/events.py` — events drill-down page
- `pages/unmatched.py` — unmatched signals page
- `pages/leads.py` — leads page (new in Phase 6)

Each page file exports a single `render()` function that `app.py` calls based on `st.session_state.current_page`.

Confirm the app runs correctly after the split before moving to Step 3.

---

### Step 3: GitHub Setup

Before Streamlit Cloud deployment can work, the repo needs to be on GitHub:

- Confirm `.gitignore` is in place and correctly excludes:
  - `.streamlit/secrets.toml`
  - `gmail_credentials.json`
  - `gmail_token.json`
  - `venv/`
  - `__pycache__/`
  - Any `.env` files
- Create a clean commit of the current codebase
- Push to a private GitHub repository
- Confirm no secrets are present in any committed files

Report the GitHub repo URL when done.

---

### Step 4: Tech Stack Field

**Supabase:**
Add a `tech_stack` column to the `accounts` table. Type: `text[]` (array of strings). Nullable.

**On the account detail page:**
In the company info section, add a Tech Stack area that shows:
- A clean list of confirmed systems currently tagged to the account
- An Edit button that opens the list for editing
- In edit mode: existing tags shown with a remove button each, plus a free text input to add new ones
- A Save button that commits changes

**On save:**
- Write the updated array to `accounts.tech_stack`
- Auto-log a dated note to `account_notes`: "Tech stack updated: added [system], removed [system]" - only mention what changed

**Search/filter:**
On the main dashboard, allow filtering accounts by tech stack term. Typing "Odoo" surfaces all accounts with Odoo in their tech stack.

**db.py additions:**
- `update_tech_stack(account_id, tech_stack_list)` — writes array to accounts table
- `search_by_tech_stack(term)` — returns accounts where tech_stack contains term (case-insensitive)

---

### Step 5: Generate Invite Button (per event)

On the account detail page, next to each event in the Events section, add a Generate Invite button.

**On click:**
Call Claude with full account context to generate a tailored event invite email.

Claude prompt:
```
You are a NetSuite sales rep inviting a prospect to an event.

Account: {account_name}
Industry: {industry}
Tech stack: {tech_stack}
Recent signals: {recent_signal_summaries}
Notes: {account_notes}

Event: {event_name}
Event date: {event_date}
Event type: {event_type}
Registration link: {registration_url}
Seismic link: {seismic_url}

Write a short, direct invite email explaining why this event is relevant to this specific company. Reference something specific about their business. Include the registration link.

Rules:
- 3-5 sentences max
- No fluff
- One clear call to action
```

**Output:**
- Display the generated invite in the Content Generation section
- Store in a new `event_invites` table (account_id, event_id, invite_body, generated_at, model_version)
- Automatically included in the briefing if the event is flagged

**db.py additions:**
- `insert_event_invite(row)` — inserts to event_invites
- `get_event_invite(account_id, event_id)` — returns stored invite if exists

Log all Claude calls to `ai_query_log`.

---

### Step 6: Flag Event for Briefing

Next to each event on the account detail page, add a Flag for Briefing toggle.

**Behavior:**
- On click: marks that account_events row as flagged
- Button reflects current flag state
- Generate Briefing only includes flagged events
- If a Generate Invite has been run for a flagged event, the invite text and both links (registration + Seismic) are included in the briefing

**Supabase:**
Add `flagged_for_briefing` boolean column (default false) to `account_events`.

**db.py additions:**
- `flag_event_for_briefing(account_id, event_id, flagged: bool)`
- `get_flagged_events(account_id)` — returns flagged events with invite text if available

Update `get_account_full_context()` to pull only flagged events and their invites for briefing assembly.

---

### Step 7: Leads Tile

**How leads arrive:**
- Brian forwards an email or photo with subject "Lead" (case-insensitive)
- Detected by: `from_email` is Brian's address AND subject is exactly "Lead"

**Processing:**
- Add `lead` to signal source detection in `signal_processor.py`
- Send image to Claude Vision to extract company name and website URL if visible
- Store original file URL from Supabase Storage
- No TAL matching - leads are explicitly not in the TAL

**Supabase - create table `leads`:**
- `id` (uuid, primary key)
- `company_name` (text, nullable)
- `website` (text, nullable)
- `file_url` (text, nullable)
- `raw_email_id` (FK to signals_raw)
- `status` (text: `active`, `dismissed`) default `active`
- `created_at` (timestamp, default now())

**Dashboard tile:**
- New tile called "Leads" showing count of active leads
- Clicking in shows list: company name, website (clickable), date captured, clickable link to original image
- Each row has a Dismiss button that sets status = dismissed

**db.py additions:**
- `insert_lead(row)`
- `get_active_leads()`
- `dismiss_lead(lead_id)`
- `get_active_lead_count()`

Log Claude Vision calls to `ai_query_log`.

---

### Step 8: SDR Field + Claimed Awaiting Briefing Tile

**How SDR emails arrive:**
- Brian forwards with subject "SDR" (case-insensitive)
- Detected by: `from_email` is Brian's address AND subject is exactly "SDR"

**Parsing:**
Email body contains a table. Extract:
- Account name (Name column)
- SDR name (BDR column) - normalize to readable format

Fuzzy match account name against TAL at 80% threshold. Below threshold goes to signal_review_queue.

**Supabase - add to `accounts` table:**
- `sdr_name` (text, nullable)
- `sdr_assigned_at` (timestamp, nullable)
- `briefing_sent_at` (timestamp, nullable) - add if not already present

**On new SDR email matching an account:**
- Overwrite `sdr_name` and `sdr_assigned_at`
- Reset `briefing_sent_at` to null so account re-enters the queue

**On account detail page:**
In company info section add SDR field showing:
- Current SDR name if assigned
- Edit button to manually update
- Dismiss button to clear the assignment

**Dashboard tile:**
- New tile called "Claimed Awaiting Briefing"
- Count of accounts where `sdr_name` is not null AND (`briefing_sent_at` is null OR `briefing_sent_at` < `sdr_assigned_at`)
- Clicking in shows list: account name, SDR name, date assigned

**Update briefing send logic:**
When Generate Briefing sends successfully, write current timestamp to `accounts.briefing_sent_at`.

**db.py additions:**
- `update_sdr(account_id, sdr_name)`
- `clear_sdr(account_id)`
- `get_claimed_awaiting_briefing()`
- `get_claimed_awaiting_count()`
- `mark_briefing_sent(account_id)`

---

### Step 9: Streamlit Cloud Deployment

**Gmail OAuth re-architecture:**
The current `gmail_token.json` was generated interactively and won't work on Streamlit Cloud. Re-architect to use a long-lived refresh token stored as a secret:

1. Extract the refresh token from existing `gmail_token.json`
2. Store in `.streamlit/secrets.toml` under `[gmail]`: `refresh_token`, `client_id`, `client_secret`
3. Update `gmail_ingest.py` to build credentials from secrets instead of token file
4. Test ingest still works after the change

**Secrets audit:**
Confirm all of the following are in `.streamlit/secrets.toml` and not hardcoded anywhere:
- Supabase URL and key
- Gmail OAuth credentials
- Anthropic API key

**requirements.txt:**
Generate a clean `requirements.txt` from the current venv. Confirm it includes: streamlit, rapidfuzz, anthropic, google-auth, google-api-python-client, supabase, and all other dependencies.

**Deploy to Streamlit Cloud:**
- Connect the GitHub repo to Streamlit Cloud
- Add all secrets from `secrets.toml` to Streamlit Cloud secrets manager
- Deploy and confirm the app loads correctly
- Confirm all Supabase data loads in the cloud-hosted version

**Cron setup on Brian's Mac:**
Set up two cron jobs so ingest and pipeline keep running locally:
1. `gmail_ingest.py` — every 15 minutes
2. `run_pipeline.py` — once per day at 7am

Provide the exact crontab entries to add.

**What stays local (does NOT move to Streamlit Cloud):**
- `gmail_ingest.py`
- `run_pipeline.py`
- `events_parser.py`

---

## Supabase Changes Summary

| Table | Change |
|-------|--------|
| `accounts` | Add `tech_stack` (text[]), `sdr_name` (text), `sdr_assigned_at` (timestamp), `briefing_sent_at` (timestamp if not present) |
| `account_events` | Add `flagged_for_briefing` (boolean, default false) |
| `leads` | Create new table |
| `event_invites` | Create new table |

---

## db.py Changes Needed (Full List)

- `update_tech_stack(account_id, tech_stack_list)`
- `search_by_tech_stack(term)`
- `insert_event_invite(row)`
- `get_event_invite(account_id, event_id)`
- `flag_event_for_briefing(account_id, event_id, flagged)`
- `get_flagged_events(account_id)`
- `insert_lead(row)`
- `get_active_leads()`
- `dismiss_lead(lead_id)`
- `get_active_lead_count()`
- `update_sdr(account_id, sdr_name)`
- `clear_sdr(account_id)`
- `get_claimed_awaiting_briefing()`
- `get_claimed_awaiting_count()`
- `mark_briefing_sent(account_id)`

---

## Outreach Tone and Structure Rules

Every outreach email and event invite generated by Claude must follow these rules without exception.

**Structure (3 parts, in order):**
1. Industry-specific hook: one sentence. Something specific and a little absurd that shows you understand their world. Written like something a rep heard in the field, not a case study. Claude should be creative and make it relevant to the account industry.
2. Signal or trigger reference: one sentence. Why you are reaching out right now.
3. CTA: direct and cheeky. Examples: "Is this something you are thinking about?" or "Let me know if this is a project you might be looking at in the next year or two." or "Happy to get you connected to the rep working this if the timing is right."

**Tone rules (hard rules, no exceptions):**
- No em dashes
- No hyphens used as dashes between phrases
- No hyphenated words
- No complex or formal vocabulary
- Short sentences only
- Sounds like a human wrote it quickly, not an AI or consultant
- A little cheeky is fine
- No filler words
- No bold font

**Length:** Two sentences plus a CTA. That is it.

**Example of the right voice (F&B industry):**
"I heard from a coworker that a company was using Post-it notes as travelers for coffee bean processing because they could not find a system that connected to QuickBooks. Saw that you registered for our CFO webinar and wanted to reach out. Is this something you are thinking about?"

**Phase 7 note:** Come back to outreach structure in Phase 7. Define a proper hook library per vertical with Brian input. Stories should come from real field experience where possible.

---

## Hard Rules

- No AI fires on page load
- Every Claude call logs to `ai_query_log`
- SDR update always resets briefing_sent_at
- Leads never fuzzy-matched to TAL accounts
- Dismissed leads never shown in UI
- Only flagged events included in briefing
- No secrets committed to GitHub
- All outreach and invite copy follows the tone and structure rules above
- Model string: `claude-sonnet-4-6`

---

## What NOT to Build in Phase 6

- One-pager generation (deferred)
- Review queue browse/resolve UI (deferred)
- Best Targets tile wiring (deferred)
- Top navigation banner (still pinned)
- Full cloud hosting of ingest/pipeline scripts

---

## Files Summary

| File | Action |
|-------|--------|
| `app.py` | Refactor — entry point and router only after split |
| `pages/dashboard.py` | Create — extracted from app.py |
| `pages/account_detail.py` | Create — extracted from app.py, add tech stack, invite, flag, SDR |
| `pages/events.py` | Create — extracted from app.py |
| `pages/unmatched.py` | Create — extracted from app.py |
| `pages/leads.py` | Create — new page |
| `signal_processor.py` | Modify — add lead and SDR source detection |
| `db.py` | Modify — all new query helpers |
| `gmail_ingest.py` | Modify — re-architect OAuth for Streamlit Cloud |
| `requirements.txt` | Create/update |

---

## Done When

- Codebase reviewed and cleaned up, report provided
- app.py split into page files, app runs correctly after split
- Repo pushed to private GitHub with no secrets committed
- Tech stack list shows on account pages, editable, saves and logs to notes, searchable
- Generate Invite button produces tailored invite per event
- Flag for Briefing toggle works, briefing only includes flagged events with links
- Leads tile shows on dashboard, vision extracts company name and website, dismiss works
- SDR field shows on account pages, auto-updates from forwarded emails, edit and dismiss work
- Claimed Awaiting Briefing tile shows correct count and list
- Briefing send marks account as briefed and removes from queue
- App loads on Streamlit Cloud with all data and no secrets exposed
- Cron jobs running on Mac for ingest and pipeline

---

## Session Notes (2026-03-28)

### Completed this session

**Outreach tone rules applied** — all 4 Claude prompts updated with the 3-part structure:
1. Industry-specific hook (absurd, field-rep voice)
2. Signal/trigger reference (why reaching out now)
3. Cheeky CTA

Prompts updated in: `signal_processor.py` (pipeline outreach), `app.py`/`pages/_account_detail.py` (Generate Outreach button, briefing fallback, Generate Invite).

**app.py split into page modules:**
- `pages/_shared.py` — go(), back_btn(), score_badge(), constants
- `pages/_dashboard.py` — home tile grid
- `pages/_tal.py` — TAL account list with filters
- `pages/_activity.py` — recent signals activity feed
- `pages/_events.py` — upcoming events table
- `pages/_misc.py` — TAL Changes and Best Targets (mock data)
- `pages/_unmatched.py` — unmatched signals review
- `pages/_leads.py` — leads + claimed awaiting briefing
- `pages/_account_detail.py` — full account detail page

Files use underscore prefix (`_`) to prevent Streamlit's `pages/` auto-discovery from showing them as top-level nav items.

**app.py** is now entry point + router only: page config, CSS, DB init, nav, password gate, chat bar, import + call page renders.

**config.py** centralized: `get_anthropic_key()`, `REP_ID`, `MODEL`, `MATCH_THRESHOLD` — all files import from here.

**GitHub** — all changes committed and pushed to `bmckeeoneill/tal-cc-v2` main branch. No secrets committed.

### Remaining for Phase 6
- Streamlit Cloud deployment (connect repo, add secrets, verify load)

### Already done — do not re-ask or re-build
- Cron jobs: running on Mac, pointing to TAL_CC_clean/venv. Ingest every 5 min M-F 8-6 PT, every 15 min off-hours. Pipeline every 5 min M-F 8-6 PT only.
- Pipeline Scout tile: live on dashboard (links to external tool via secrets)
- Quick Links bar: live on dashboard
- All Phase 6 steps 1–8: complete (cleanup, page split, GitHub, tech stack, generate invite, flag for briefing, leads tile, SDR + claimed awaiting briefing)
- Outreach tone rules applied to all Claude prompts

---

## Session Notes (2026-04-01)

### Completed this session

**Venv rebuilt** — venv had hardcoded paths from old project location. Deleted and recreated at `TAL_CC_clean/venv/`, reinstalled from requirements.txt.

**Event date year inference fixed** — `_infer_year()` now uses signal's `received_at` date as reference instead of today. Events within 60 days before received date keep current year. Fixed 70 existing 2027 events → 2026 in DB.

**Claude fallback for events parser** — if regex parser finds nothing, falls back to Claude to extract events from unstructured email body. Same output shape, same downstream processing.

**One pager attached to briefing** — if one pager has been generated this session, it auto-attaches as HTML file when briefing is sent. No checkbox needed — green button state is the signal.

**Signal dedup** — `get_signals_for_account()` now deduplicates by `raw_id` so same source email doesn't appear as multiple signals.

**Screenshot headlines** — screenshot signals now get a readable headline (`Company: Signal Type`) instead of the raw filename.

**Similar Customers feature** — full implementation:
- pgvector enabled in Supabase, `customers` table created with ivfflat index
- `match_customers` RPC function deployed
- `load_customers.py` ingests from `customers.csv` in project root (5,750 rows loaded)
- `embed_text()` and `get_similar_customers()` added to `db.py`
- Before embedding, Claude scrapes the account's website and summarizes what the company does — used as query text. Falls back to company name + industry if scrape fails.
- TAL accounts filtered from results using rapidfuzz at 85% threshold
- Returns 5 results, cached in session state (no re-fetch on page interactions)
- Similar Customers button in Content Generation section (4-column layout)
- Results included in briefing email if fetched this session
- OpenAI key in `.streamlit/secrets.toml` under `[openai]`
- `openai==2.30.0` added to requirements.txt
- Migration: `migrations/007_similar_customers.sql`

### Remaining for Phase 6
- Streamlit Cloud deployment (connect repo, add secrets, verify load)
- Outreach tone rules applied to all Claude prompts
