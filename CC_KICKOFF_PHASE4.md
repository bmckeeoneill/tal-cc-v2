# TCC Phase 4 — AI Logic Layer
## Claude Code Kickoff Document

---

## Context

TAL Command Center (TCC) is a Streamlit app running on port 8501. It manages 296 Oracle NetSuite territory accounts. The backend is Supabase. Phase 4 adds the AI processing pipeline, account notes, a Claude chat popup, and a home button.

Working directory: `/Users/brianoneill/Desktop/TAL_CC_clean`
Python: 3.14, venv at `venv/`
AI model: `claude-sonnet-4-6`

---

## What Phase 4 Builds

1. Supabase Storage bucket for attachments
2. Gmail ingest update: upload attachments to bucket, store file URL
3. Signal source detection: screenshot forward vs. CRM notification vs. text forward
4. Signal extraction + company name identification
5. Fuzzy account matching
6. Review queue routing
7. Per-signal AI summary (vision for screenshots, structured parse for CRM, text for forwards)
8. Weekly account analysis
9. Weekly digest scoring
10. Outreach suggestion (POC stub)
11. Account notes (plain text, per account, date stamped)
12. Claude chat popup (available everywhere, session memory, page-aware context)
13. Home button on every non-home page

---

## Build Order and Specs

### Step 1: Supabase Storage Bucket

Create a storage bucket called `signal-attachments` in Supabase. Set it to private. CC handles this via migration or Supabase API - Brian does not touch the Supabase dashboard.

Add a `file_url` column to `signals_raw` if it does not already exist.

---

### Step 2: Update gmail_ingest.py

When a qualifying email has attachments:

- Decode the base64 attachment
- Upload it to the `signal-attachments` bucket
- File path in bucket: `{rep_id}/{signal_id}/{filename}`
- Save the resulting signed URL back to `signals_raw.file_url`
- Still store attachment metadata in the `attachments` jsonb field as before

Screenshots will be `.png` or `.jpg`. PDFs: store the file URL, do not parse yet.

---

### Step 3: Signal Source Detection

Before any extraction runs, classify each `signals_raw` row by source:

- `from_email` is `unknown-email@nlcorp.com` → source = `crm_notification`
- `from_email` is Brian's address AND there is a `file_url` with an image extension → source = `screenshot_forward`
- `from_email` is Brian's address AND no attachment → source = `text_forward`

Carry `source` through the processing pipeline.

---

### Step 4: Signal Extraction

**File to create:** `signal_processor.py`

For each unprocessed row in `signals_raw` (where `processed = false`):

**Path A: CRM notification** (`source = crm_notification`)

Parse the email body directly. No Claude needed:
- Company name: extract from "Associated companies, contacts:" line (everything before the first comma)
- Contact name: everything after the first comma on the same line
- Signal type: derive from subject line keywords:
  - "Registered for" or "Virtual Event" → `event`
  - "Intent Signal" or "ZoomInfo" → `intent_signal`
  - "Did Not Attend" → `event`
  - "Webinar" → `event`
  - Default → `crm_other`
- Signal body: the full "Task:" field value from the email body

**Path B: Screenshot forward** (`source = screenshot_forward`)

Send the image to Claude Vision. Prompt:
```
You are analyzing a screenshot forwarded by a sales rep. Extract the following:
1. Company name (if visible)
2. What is happening (1-2 sentences)
3. Why this is relevant to a NetSuite sales rep (1 sentence)
4. Signal type: one of exec_hire, funding, tech_adoption, expansion, event, other

Return only a JSON object with keys: company_name, what_happened, why_relevant, signal_type
```

**Path C: Text forward** (`source = text_forward`)

Send subject line to Claude. Prompt:
```
Extract the company name from this email subject line. Return only the company name, nothing else. If you cannot identify a company name, return null.

Subject: {subject}
```

Then extract signal type from subject + body. Signal types: `exec_hire`, `funding`, `tech_adoption`, `expansion`, `event`, `other`

Log every Claude call to `ai_query_log` (prompt, model, timestamp, signal_id).

---

### Step 5: Fuzzy Account Matching

Still inside `signal_processor.py`.

After extracting the company name from any path:

- Load all account names from the `accounts` table
- Run fuzzy match using `rapidfuzz` against `company_name` field
- Threshold logic:
  - 80%+ match → auto-assign to that account, write `account_id` to the processed signal
  - Below 80% → route to `signal_review_queue` with extracted name, best guess match, and confidence score
  - Null company name → route to `signal_review_queue` with reason "no company name found"

---

### Step 6: Review Queue Routing

When a signal goes to `signal_review_queue`, insert a row with:
- `signal_id` (FK to signals_raw)
- `extracted_name` (what was pulled from the email)
- `best_match_name` (top fuzzy candidate, even if below threshold)
- `confidence_score` (0-100)
- `reason` (e.g. "low confidence match" or "no company name found")
- `status` = `pending`
- `created_at`

Wire the Unmatched tile count on the dashboard to the number of rows in `signal_review_queue` where `status = pending`. This is a `db.py` change only, not a UI redesign.

---

### Step 7: Per-Signal AI Summary

For every signal that clears the 80% threshold:

**CRM notifications:** Send the Task field content to Claude for a 2-sentence summary: what happened and why it matters for a NetSuite rep.

**Screenshot forwards:** The vision extraction in Step 4 already produced `what_happened` and `why_relevant`. Combine them into the summary field directly - no second Claude call needed.

**Text forwards:** Send subject + body to Claude for a 2-3 sentence summary.

Write to `signals_processed`:
- `account_id`
- `signal_type`
- `summary`
- `source` (crm_notification, screenshot_forward, text_forward)
- `file_url` (if present, for clickable file access in the UI)
- `source_signal_id` (FK to signals_raw)
- `processed_at`
- `model_version`

Mark the corresponding `signals_raw` row as `processed = true`.

---

### Step 8: Weekly Account Analysis

**Function:** `run_weekly_analysis(account_id)`

Pull all `signals_processed` rows for that account from the last 7 days. Send to Claude:
- What is happening at this account?
- What is the overall signal trend?
- Is this account heating up, cooling down, or flat?

Write to `weekly_analysis`:
- `account_id`
- `week_of` (Monday of current week)
- `summary`
- `trend` (one of: `heating`, `cooling`, `flat`)
- `generated_at`
- `model_version`

Always insert a new row. Never overwrite prior weeks.

---

### Step 9: Weekly Digest Scoring

**Function:** `run_weekly_digest()`

Pull all accounts with signals processed in the last 7 days. Score each 1-10 based on:
- Number of signals this week
- Signal types (exec hire and funding weight higher)
- Trend from weekly_analysis

Write top accounts to `weekly_digest`:
- `week_of`
- `account_id`
- `score`
- `reasoning` (1-2 sentences)
- `generated_at`

Surface the top 5 accounts. These will eventually power the Best Targets tile (wiring is Phase 5).

---

### Step 10: Outreach Suggestion (POC Stub)

For each matched signal, generate one outreach email suggestion.

Claude prompt:
```
You are a NetSuite sales rep. Write a short, direct outreach email based on this buying signal.

Signal type: {signal_type}
Company: {company_name}
Signal summary: {summary}

Rules:
- 3-5 sentences max
- No fluff
- Reference the specific signal
- One clear call to action
```

Write to `outreach_templates`:
- `account_id`
- `signal_id`
- `trigger_type` (same as signal_type)
- `email_body`
- `generated_at`
- `model_version`

POC only. No vertical logic yet.

---

### Step 11: Account Notes

**Supabase - create table `account_notes`:**
- `id` (uuid, primary key)
- `account_id` (FK to accounts)
- `note_text` (text)
- `created_at` (timestamp, default now())

**db.py additions:**
- `save_note(account_id, note_text)` — inserts a row to account_notes
- `get_notes(account_id)` — returns all notes for that account ordered by created_at desc

**app.py changes:**

On the account detail page, add a notes section below existing content:
- `st.text_area` for input
- Save button that calls `save_note()` and clears the input on success
- List of prior notes below, each showing note text and formatted timestamp, newest first

---

### Step 12: Claude Chat Popup

**Feature:** A fixed "Ask Claude" button in the bottom-right corner of every page. Always visible. Clicking it opens a chat panel.

**On open:**
- If on an account detail page: pre-seed context with that account's name, recent signals (last 7 days), and all notes
- If on the main dashboard or any other page: pre-seed with a one-liner summary of all 296 accounts (name, industry, signal count this week)

**Chat behavior:**
- Standard message input - user types, hits Send, Claude responds
- Conversation history in `st.session_state.chat_history` as a list of `{role, content}` dicts
- Clears when browser session resets
- No Supabase storage of chat history for now

**System prompt on every call:**
```
You are an AI assistant embedded in a NetSuite sales rep's Territory Account List tool called TAL Command Center. You help with account research, prioritization, outreach ideas, and anything else relevant to managing a sales territory.

Current page context:
{page_context}
```

Full conversation history passed as the messages array.

**Implementation notes:**
- Fixed-position button in app.py, visible on all pages
- Chat panel as Streamlit sidebar or modal - CC decides what is cleanest
- `st.session_state.chat_page_context` set when each page loads
- Model: `claude-sonnet-4-6`
- Log every Claude call to `ai_query_log`

**db.py additions:**
- `get_account_chat_context(account_id)` — returns account name, industry, recent signal summaries, and notes as a formatted string
- `get_tal_summary_context()` — returns a one-liner per account across all 296 (name, industry, signal count this week)

---

### Step 13: Home Button

On every non-home page (account detail pages, tile drill-down pages, etc.) add a Home button at the top of the page.

On click: set `st.session_state.current_page = 'home'` and call `st.rerun()`.

Keep it simple - a standard `st.button('Home')` at the top of the page content is fine. No styling changes required.

---

## Runner Script

**File to create:** `run_pipeline.py`

Orchestrates the full pipeline in order:

1. Process all unprocessed `signals_raw` rows (Steps 3-7)
2. Run `run_weekly_analysis()` for every account that got new signals
3. Run `run_weekly_digest()`
4. Print a summary: X signals processed, X routed to review queue, X accounts updated

Run manually for now. Scheduling comes later.

---

## db.py Changes Needed (Full List)

- `get_unprocessed_signals()` — all signals_raw where processed = false
- `get_account_names()` — list of (id, company_name) from accounts
- `insert_signals_processed(row)` — inserts to signals_processed (must accept file_url and source)
- `insert_review_queue(row)` — inserts to signal_review_queue
- `get_pending_review_count()` — count of signal_review_queue where status = pending
- `get_signals_for_account(account_id, days=7)` — signals_processed for an account in last N days
- `upsert_weekly_analysis(row)` — inserts new row to weekly_analysis, never overwrites
- `insert_weekly_digest(rows)` — inserts scored accounts for the week
- `insert_outreach_suggestion(row)` — inserts to outreach_templates
- `log_ai_call(row)` — inserts to ai_query_log
- `upload_attachment_to_storage(file_bytes, path)` — uploads to signal-attachments bucket, returns signed URL
- `save_note(account_id, note_text)` — inserts to account_notes
- `get_notes(account_id)` — all notes for account, newest first
- `get_account_chat_context(account_id)` — formatted account context string for chat
- `get_tal_summary_context()` — one-liner per account for chat context

---

## Hard Rules

- `signals_raw` is append-only. Never modify or delete rows.
- Every Claude API call logs to `ai_query_log`: prompt, model version, timestamp, signal_id.
- Low-confidence matches always go to `signal_review_queue`. Never silently dropped.
- Weekly analysis always inserts a new row. Never overwrites prior weeks.
- Model string to use: `claude-sonnet-4-6`

---

## What NOT to Build in Phase 4

- PDF parsing (store the file URL, do not parse content yet)
- Vertical-specific outreach logic (POC stub only)
- Review queue UI beyond wiring the Unmatched tile count
- Best Targets tile wiring (digest scoring built, UI wiring is Phase 5)
- Top navigation banner (pinned for later)

---

## Files Summary

| File | Action |
|------|--------|
| `gmail_ingest.py` | Modify — upload attachments to Supabase Storage, store file_url |
| `signal_processor.py` | Create — steps 3 through 7 |
| `run_pipeline.py` | Create — orchestrator |
| `db.py` | Modify — add all new query helpers |
| `app.py` | Modify — Unmatched tile count, account notes UI, Claude chat popup, home button |

---

## Done When

- ✅ `run_pipeline.py` runs end to end without errors
- ✅ A forwarded screenshot gets uploaded to Supabase Storage, vision-extracted, matched, summarized, and written to signals_processed with a file_url
- ✅ A CRM notification email gets parsed, matched, summarized, and written to signals_processed
- ✅ Low-confidence signals appear in signal_review_queue
- ✅ Unmatched tile count reflects pending review queue rows
- ✅ Outreach suggestion generated and stored for at least one matched signal
- ✅ All Claude calls logged to ai_query_log
- ✅ Account notes save and display correctly on the account detail page
- ✅ Claude chat available on every page — implemented as horizontal bar at top (not sidebar popup); pre-seeds with account context or full TAL summary; maintains session history; Enter key submits
- ✅ Home button appears on every non-home page and navigates back correctly

---

## What Changed During Build (vs. Original Spec)

- **Chat popup → horizontal bar**: Sidebar approach abandoned due to Streamlit CSS hiding the sidebar element. Replaced with a full-width chat bar at the top of every page with inline response display and a "Full conversation" expander.
- **fuzzy matching**: Switched from `token_sort_ratio` to `token_set_ratio` and added name normalization (strip punctuation, strip legal suffixes like inc/llc/corp) to improve match quality.
- **Confidence cap**: `signals_processed.match_confidence` is `numeric(4,2)` — max 99.99. Capped in code.
- **Weekly analysis scope**: Originally would have looped all 296 accounts. Changed to only run for accounts that received new signals in the last 7 days (single query first to find active accounts).
- **Notes key pattern**: `st.session_state[key] = ""` throws after widget instantiation. Fixed with a counter-based key (`note_input_{account_id}_{counter}`) incremented on save.
- **Outreach text_area label**: Empty label `""` caused Streamlit crash before sidebar rendered. Fixed with `label_visibility="collapsed"`.

## Known Issues / Not Yet Built

- Review queue UI: tile count wired, but no UI to browse/resolve queue items beyond the Unmatched page
- Best Targets tile: digest scoring built and stored, UI wiring deferred to Phase 5/6
- Chat context for events: not included in TAL summary context (added in Phase 5)
