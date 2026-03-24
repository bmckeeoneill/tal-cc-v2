# TAL Command Center — Planning Doc

Last updated: March 2026  
Status: Phase 1 UI in progress

---

## What This Is

A dedicated account management hub built as an extension of Pipeline Scout. One landing page per TAL account. Captures signals from multiple sources, runs AI analysis, and surfaces the best accounts to contact each week with suggested outreach.

The problem it solves: too many signals across 300+ accounts with no central place to connect the dots. This system captures everything, links smaller signals over time, and tells you what actually matters.

---

## Accounts

- 295 accounts in the TAL, sourced from `TAL/brian_tal.csv` (updated weekly, same file, same location)
- App reads directly from the CSV — when the file is swapped, data updates automatically
- Each account has a linked NetSuite NSCORP record
- TAL updates weekly — Pipeline Scout ingest handles the sync (needs to be confirmed and tested)
- Every table has a `rep_id` field from day one so other reps can use this with a different account list

---

## How Data Gets In

### Pipeline Scout signals
- Buying triggers already captured by Pipeline Scout feed directly into this system
- Confirm the existing ingest works for the TAL sync

### Email ingest (manual signals)
- Forward anything to a dedicated address: screenshots, articles, links, PDFs, marketing emails, event announcements, plain text notes
- Postmark inbound webhook receives the email and posts a JSON payload (body + base64 attachments) to a simple receiver endpoint
- Receiver validates, timestamps, and inserts raw payload into `signals_raw` — no processing in the receiver
- Claude Code processes from `signals_raw` and writes cleaned output to `signals_processed`
- The staging table pattern gives a full audit trail and makes it easy to reprocess if extraction logic improves
- Decision: Postmark over Zapier — cleaner attachment handling, no external dependency, owned pipe

---

## Signal Processing Logic

Two-pass classification on every incoming signal:

**Pass 1 — Signal type**
- Is this account-specific (exec hire, funding round, tech adoption)?
- Or is this a global event (conference, product launch, industry news)?

**Pass 2 — Tagging**
- Account-specific: fuzzy match company name to TAL account, tag to that account
- Global event: fan out to relevant accounts based on vertical, size, or other criteria
- Low-confidence matches (below 80%) go to `signal_review_queue` — never silently dropped
- Files (screenshots, PDFs) stored in Supabase Storage and linked from the review queue item

### Unmatched signals UI
- Dashboard has a dedicated "Unmatched Signals" tile styled in Brand Yellow to stand out
- Each unmatched item shows: content type, AI summary, date received, link or preview of original content
- "Tag to Account" button lets you manually match it from a dropdown of TAL accounts
- This is the review queue UI — Phase 4 wires the backend logic

---

## What Lives on Each Account Page

- Full signal history (Pipeline Scout + manually forwarded)
- AI-generated summary for each signal
- Running analysis updated weekly
- Suggested outreach based on recent triggers and upcoming events
- Relevant NetSuite content (case studies, ROI assets, one-pagers) tagged by vertical
- AI-generated one-pager per account (regeneratable, saveable — versions never overwritten)
- NSCORP record link
- Last touched / next action fields

---

## Weekly Digest

Lives in the "Best Targets" tile/tab. Answers: who should I contact this week and why.

**Scoring model (draft):**
- Signal type weight: CFO hire = high, press release = low
- Recency decay: signals older than 30 days lose weight
- Event proximity boost: conference in 2 weeks = score multiplier
- Cumulative volume: 5 small signals in a week beats 1 isolated signal
- Pattern combinations: multiple signal types for same account in short window = priority flag

Keep the scoring logic simple enough to explain why any account surfaced.

---

## Natural Language Query (Phase 4 feature)

A chat input on the dashboard that lets you ask questions about your signal data in plain English.

**How it works:**
1. You type a question (e.g. "how have my inputs been trending")
2. App pulls relevant data from Supabase based on the question type
3. Sends data + question to claude-sonnet-4-20250514
4. Renders the answer inline on the dashboard

**Example questions it should handle:**
- "How have my inputs been trending"
- "Which accounts have had the most signals this month"
- "Any manufacturing accounts with CFO hires in the last 30 days"
- "What did I forward last week that didn't match an account"
- "Which events have the most TAL accounts flagged"

**Implementation notes:**
- No MCP needed — app does the Supabase query, passes data as context to Claude
- Log prompt used, model version, and timestamp alongside every response in Supabase
- Keep query routing simple: classify question type first, then pull the right data slice

---

## Email Outreach Templates

- Base template driven by trigger type (the "why reach out now" hook)
- Vertical-specific language and proof points swapped in on top
- NetSuite content assets pulled from library based on account vertical
- Logic: trigger type selects template structure, vertical fills in the specifics
- Easier to maintain than a full trigger x vertical matrix

---

## NetSuite Content Library

- Stored in Supabase with vertical tags and content type tags (case study, ROI calculator, one-pager)
- Needs an initial upload step to populate
- Simple admin UI to manage the library (Phase 4 or later)
- Outreach generator pulls top 1-2 assets by vertical match

---

## One-Pagers

- AI-generated per account, not manually written
- Pulls from: signal history, NSCORP record, vertical context
- Output: short "why NetSuite makes sense for [Account]" brief
- UI has a "regenerate" button and a "save this version" option
- Never overwrite saved versions — append new ones, let user choose

---

## Dashboard UI Structure

### Homepage
- Compact header (utility tool, not marketing)
- "What's New" callout box: category counts only, each item drillable to the relevant tab
- Grid of large clickable tiles — entire tile is clickable, not just a link
- Single-page app using st.session_state.current_page — no page reloads, no re-auth on tile click

### Tiles
| Tile | Color | Content |
|---|---|---|
| TAL | Ocean 120 #36677D | Account count, industries, states |
| Recent Activity | Ocean 120 #36677D | Updates in last 7 days |
| Events | Ocean 120 #36677D | Upcoming events, this month count |
| TAL Changes | Ocean 120 #36677D | Added/removed this week |
| Best Targets | Ocean 120 #36677D | Top accounts to contact |
| Unmatched Signals | Brand Yellow #E2C06B | Items that didn't map to a TAL account |

---

## NetSuite Brand Color Palette

| Name | Hex | Usage |
|---|---|---|
| Neutral 30 | #F1EFED | Page background, sidebar |
| Ocean 180 | #13212C | Primary text, headings |
| Ocean 120 | #36677D | Buttons, active tabs, tile backgrounds, links |
| Ocean 60 | #94BFCE | Borders, hover states, secondary accents |
| Ocean 30 | #E7F2F5 | Card backgrounds, subtle fills |
| Brand Yellow | #E2C06B | Unmatched signals tile, badges only |

Rule: light surfaces for reading, Ocean 120 for clicking. Nothing outside these six colors.

---

## Supabase Tables (draft)

| Table | Purpose |
|---|---|
| `accounts` | TAL account list, rep_id, NSCORP link, vertical, metadata |
| `signals_raw` | Raw Postmark ingest — append-only, never modified |
| `signals_processed` | Extracted, tagged, summarized signals |
| `signal_review_queue` | Low-confidence matches with reason, waiting for manual review |
| `weekly_analysis` | Per-account weekly AI analysis output |
| `outreach_templates` | Base templates by trigger type |
| `content_library` | NetSuite assets tagged by vertical and content type |
| `account_content` | Generated one-pagers, all saved versions |
| `weekly_digest` | Top accounts to contact each week with scoring |
| `ai_query_log` | Natural language queries, prompt used, model version, timestamp |

---

## Tech Stack

| Layer | Tool |
|---|---|
| Backend / database | Supabase (already partially set up) |
| Email ingest | Postmark inbound webhook |
| AI model | claude-sonnet-4-20250514 |
| Frontend | Streamlit (same as Pipeline Scout) |
| Planning / prompts | This Claude.ai project |

---

## Build Sequence

### Phase 1 — Dashboard shell (in progress)
Streamlit UI with real TAL data from TAL/brian_tal.csv. Static hardcoded data for signals, events, changes. Every field visible. No backend writes yet.
Output: exact Supabase schema requirements.

### Phase 2 — Data layer + TAL sync
Build Supabase schema from Phase 1 output. Wire Pipeline Scout TAL sync. Confirm weekly refresh. Dashboard shows real account data, no signals yet.

### Phase 3 — Postmark email ingest
Set up Postmark inbound address. Receiver endpoint writes raw payload to signals_raw. No AI yet. Confirm the pipe works and raw content (including attachments) arrives cleanly. Test with real forwards.

### Phase 4 — AI logic
- Signal extraction and account tagging
- Fuzzy match + global event fanout
- Per-signal AI summaries
- Weekly running analysis per account
- Weekly digest scoring
- Outreach suggestion generation
- Review queue for low-confidence matches
- One-pager generation
- Natural language query interface

---

## Portability

Other reps can use this with minimal setup. Same job, same product, different account list. Swapping in a new TAL CSV is all it takes — rep_id on every table handles the separation. Keep all logic flexible, no hardcoded account assumptions.

---

## Open Questions

- [ ] Confirm Pipeline Scout TAL sync handles weekly updates cleanly
- [ ] Define vertical taxonomy for content library tagging
- [ ] Nail down signal type list and weights for the digest scoring model
- [ ] Confirm Supabase Storage plan supports file attachments at expected volume

---

## This Project's Role

Claude.ai (this project) = thinking layer  
Claude Code = execution layer

Use this project to:
- Work through architecture and edge cases
- Draft and iterate on prompts for signal extraction and analysis
- Design the scoring model and outreach template logic
- Review AI output quality and tune system prompts

Use Claude Code to:
- Build and run the actual code
- Set up Supabase schema and migrations
- Wire Postmark and test ingestion
- Run the weekly analysis and digest jobs
