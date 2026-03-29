# TCC Phase 5 — Events + Content Generation
## Claude Code Kickoff Document

---

## Context

Continuing from Phase 4. TCC is running on port 8501 with 296 accounts, Gmail ingest live, signal processing pipeline built, account notes working, and Claude chat popup in place.

Working directory: `/Users/brianoneill/Desktop/TAL_CC_clean`
Python: 3.14, venv at `venv/`
AI model: `claude-sonnet-4-6`

---

## What Phase 5 Builds

1. Events ingestion from forwarded MMTT emails
2. Events table in Supabase
3. Events matching to accounts (location for in-person, all accounts for webinars)
4. Events tile drill-down view
5. Relevant events section on each account detail page
6. Content Generation section on each account detail page (button-triggered only)
7. Generate Outreach button
8. Generate Briefing button (emails assembled package to Brian)

---

## Build Order and Specs

### Step 1: Events Table

Create table `events` in Supabase:
- `id` (uuid, primary key)
- `event_name` (text)
- `event_date` (date)
- `event_type` (text: `webinar`, `in_person`, `competitive`, `evergreen`)
- `region` (text, nullable - for in-person events e.g. "Florida", "Texas", "Central")
- `registration_url` (text, nullable - NSCorp search link)
- `seismic_url` (text, nullable)
- `raw_email_id` (FK to signals_raw)
- `created_at` (timestamp, default now())

Create junction table `account_events`:
- `id` (uuid, primary key)
- `account_id` (FK to accounts)
- `event_id` (FK to events)
- `match_reason` (text: `location_match` or `webinar_all`)
- `created_at` (timestamp, default now())

---

### Step 2: Events Ingestion

**How events emails arrive:**
- Forwarded by Brian from his Gmail addresses
- Subject line will be "Events" (Brian will use this consistently)
- Detect by: `from_email` is Brian's address AND subject is exactly "Events" (case-insensitive)

**Add to signal source detection in `signal_processor.py`:**
- Source = `events_digest` when subject matches "Events"

**Create `events_parser.py`:**

Parse the email body to extract individual events. The MMTT email has a consistent structure:

- Events are listed as bullet points with format: `DATE - EVENT NAME<URL> - Seismic Page<URL>`
- Sections are labeled: `Evergreen`, `Competitive`, `Upcoming In-Person Events`
- In-person events have region sub-headers (e.g. `Central`, `Florida`, `Texas`)

Extract for each event:
- Event name (text between date and first URL)
- Event date (parse from the date prefix, e.g. "3/25")
- Event type: derive from section header
  - Under "Evergreen" → `evergreen`
  - Under "Competitive" → `competitive`
  - Under "Upcoming In-Person Events" → `in_person`
  - Anything with "webinar" in the name → `webinar`
- Region: the sub-header under "Upcoming In-Person Events" (e.g. "Florida", "Texas")
- Registration URL: the NSCorp link (nlcorp.app.netsuite.com)
- Seismic URL: the seismic.com link

Write each event to the `events` table. Skip duplicates (match on event_name + event_date).

Year inference: the email doesn't always include the year. Use current year, but if the month is earlier than the current month, use next year.

---

### Step 3: Account-Event Matching

Run after events are parsed. For each new event:

**Webinars and evergreen/competitive events:**
- Match to ALL accounts
- `match_reason` = `webinar_all`

**In-person events:**
- Match to accounts where the account's state or region field matches the event region
- Use fuzzy matching on region name (e.g. "Florida" matches accounts with state "FL" or "Florida")
- `match_reason` = `location_match`

Write matches to `account_events`.

**db.py additions:**
- `insert_event(row)` — inserts to events table
- `get_events_for_account(account_id)` — returns upcoming events for an account (event_date >= today), joined from account_events
- `get_all_upcoming_events()` — returns all events where event_date >= today, ordered by event_date
- `get_upcoming_event_count()` — count of events where event_date >= today (for dashboard tile)

---

### Step 4: Events Tile Drill-Down

The Events tile on the main dashboard already exists and shows a count. Wire it so clicking opens a drill-down view showing all upcoming events in a table:

Columns: Date, Event Name, Type, Region (if in-person), Registration Link, Seismic Link

Sort by event_date ascending. Past events not shown.

This is an `app.py` change. Use `st.session_state.current_page = 'events'` to navigate.

---

### Step 5: Relevant Events on Account Detail Page

On each account detail page, add an Events section (always visible, no AI cost):

- Show upcoming events matched to that account from `account_events`
- Display: date, event name, type, and clickable registration + Seismic links
- If no upcoming events: show "No upcoming events matched to this account"
- Sort by event_date ascending

---

### Step 6: Content Generation Section

On each account detail page, add a "Content Generation" section below the events section.

This section is clearly separated from the rest of the page. It contains buttons that trigger AI generation on demand. Nothing in this section runs automatically when the page loads.

**Important:** No AI calls fire on page load. Every action in this section is button-triggered.

---

### Step 7: Generate Outreach Button

Inside the Content Generation section.

On click:
1. Check if an outreach suggestion already exists in `outreach_templates` for this account (from Phase 4 pipeline)
2. If yes: display it immediately, no new Claude call
3. If no: call Claude to generate one using the same prompt from Phase 4

Display the generated email in a text area so Brian can read and copy it.

Add a Regenerate button below it that forces a new Claude call even if one exists.

Log all Claude calls to `ai_query_log`.

---

### Step 8: Generate Briefing Button

Inside the Content Generation section.

On click, assembles a briefing package from already-stored data (no extra AI cost if outreach already generated):

**Briefing contents:**
1. Account name and basic info
2. Recent signals (last 30 days) with AI summaries
3. Upcoming relevant events with registration links
4. Outreach draft (generate if not already exists, otherwise use stored version)
5. Notes added by Brian

**Delivery:**
- Send the assembled briefing as an email to `brian.br.oneill@oracle.com`
- Use Gmail API (already authenticated) to send
- Subject: `TCC Briefing: {account_name} - {today's date}`
- Body: plain text formatted for easy forwarding to an SDR

**Email format:**
```
TCC Account Briefing
Account: {account_name}
Date: {today}

--- SIGNALS ---
{list of recent signals with dates and summaries}

--- UPCOMING EVENTS ---
{list of relevant events with dates, names, and registration links}

--- OUTREACH DRAFT ---
{generated outreach email}

--- NOTES ---
{list of notes with dates}
```

Show a success message in the UI after the email is sent.

Log the send action (not a Claude call, but log to a simple sent_briefings table or just print to console for now).

**db.py additions:**
- `get_account_full_context(account_id)` — pulls signals, events, outreach, and notes for one account in one call for briefing assembly

---

## Files Summary

| File | Action |
|------|--------|
| `events_parser.py` | Create — parses MMTT email body, writes to events table, runs account matching |
| `signal_processor.py` | Modify — add `events_digest` source detection, call events_parser when detected |
| `app.py` | Modify — events tile drill-down, events section on account page, content generation section |
| `db.py` | Modify — add all new query helpers |

---

## db.py Changes Needed (Full List)

- `insert_event(row)` — inserts to events, skips duplicates on name + date
- `get_events_for_account(account_id)` — upcoming events for one account
- `get_all_upcoming_events()` — all upcoming events sorted by date
- `get_upcoming_event_count()` — count for dashboard tile
- `get_account_full_context(account_id)` — signals, events, outreach, notes for briefing

---

## Hard Rules

- Nothing in the Content Generation section fires on page load
- Every Claude call logs to `ai_query_log`
- Briefing email sends to `brian.br.oneill@oracle.com` only
- Past events never shown in UI (filter event_date >= today always)
- Events table deduplicates on event_name + event_date
- Model string: `claude-sonnet-4-6`

---

## What NOT to Build in Phase 5

- One-pager generation (later)
- Vertical-specific outreach logic (still POC)
- Top navigation banner (still pinned)
- Best Targets tile wiring (Phase 6)
- Natural language query interface (already built in Phase 4, no changes needed)

---

## Done When

- ✅ Forwarding an email with subject "Events" parses and stores all events from the MMTT digest
- ✅ Events tile drill-down shows all upcoming events
- ✅ Account detail pages show relevant matched events
- ✅ Content Generation section visible on every account page
- ✅ Generate Outreach button produces and displays a draft email (uses stored pipeline outreach if exists; Regenerate forces new Claude call)
- ✅ Generate Briefing button sends a formatted email to Brian with all account context (signals, events, outreach, notes, NS record link)
- ✅ All Claude calls logged
- ✅ Events context included in Claude chat TAL summary (event list + matched account counts)
- ✅ NS record URL included in briefing email

---

## What Changed During Build (vs. Original Spec)

- **events table already existed**: Phase 1 created an `events` table with a different schema (name, location, virtual, etc.). Migration 005 added the Phase 5 columns alongside; `insert_event()` populates legacy `name` column to satisfy NOT NULL constraint.
- **Parser format**: Actual MMTT email uses `  *   DATE - Event Name<URL> - Seismic Page<URL>` bullet format, not bare date-prefixed lines. Parser updated to strip `  *   ` bullet prefix and handle em-dashes and spaced dates (`3 /4`).
- **"Industry" section**: MMTT has an "Industry" section not mentioned in spec. Mapped to `evergreen` type.
- **Year inference**: Parser infers year from date — if month/day is already past relative to today, uses next year. Old MMTT emails (Feb 2026) land in 2027; a current week's email will land in the correct year.
- **PostgREST join ordering**: `.order("events.event_date")` on a joined table throws a parse error in PostgREST. Fixed by fetching without order and sorting in Python.
- **`get_tal_summary_context()`**: Extended to include upcoming events list and per-event matched account counts, so Claude chat can answer questions about events.
- **Briefing email fallback**: If Gmail API send fails, briefing text is shown in a text_area for manual copy.

## Known Issues / Not Yet Built

- **Events dedup on re-forward**: If Brian forwards the same MMTT again, the unique index on `event_name + event_date` prevents duplicate rows — this works correctly. But the signal is already marked processed, so re-processing requires calling `events_parser.process_events_email()` directly.
- **Region matching**: Canadian provinces (Ontario, Alberta, BC, Quebec) and "District of Columbia" / "Washington D.C." don't map to US state codes — in-person events in those regions won't match US accounts. Acceptable for now.
- **Best Targets tile**: Still using mock data — wiring to weekly_digest deferred to Phase 6.
- **One-pager generation**: Not built (deferred).
- **Review queue UI**: Still only the count tile; no full browse/resolve UI.
