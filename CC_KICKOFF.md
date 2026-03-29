# TAL Command Center — CC Project Instructions

Paste this as your first message when starting a new CC session on this project.

---

## Kickoff Prompt

You are building the TAL Command Center, an account management hub that extends Pipeline Scout. Before doing anything else:

1. Read `CLAUDE.md` — this governs how you work on this project
2. Read `PLANNING.md` — this is the full architecture and decision log
3. Read `tasks/todo.md` if it exists — check for open items from the last session
4. Read `tasks/lessons.md` if it exists — review patterns from previous sessions

Do not write any code until you have read all four files and confirmed you understand the current state of the project.

---

## Project Summary (for context)

TAL Command Center is a dedicated per-account landing page system for 311 NetSuite sales accounts. It captures buying signals from multiple sources, runs AI analysis, and surfaces the best accounts to contact each week with suggested outreach.

**Stack:**
- Supabase (existing instance, shared with Pipeline Scout)
- Postmark inbound email webhook for signal ingestion
- Claude API (claude-sonnet-4-20250514) for signal extraction, analysis, and outreach generation
- Pipeline Scout frontend as the starting point

**Build sequence:**
1. Dashboard shell (static UI, defines data requirements)
2. Data layer and TAL sync (Supabase schema, Pipeline Scout sync confirmed)
3. Postmark email ingest (raw signals to staging table)
4. Claude Code logic (extraction, tagging, analysis, digest, outreach)

**Current status:** Pre-build. Architecture decided. No code written yet.

---

## First Session Task

Build the dashboard shell — Phase 1.

Goal: a static account page UI with hardcoded placeholder data that shows every field we want on the final product. No backend. No live data. Just the UI.

Fields to include on the account page:
- Account name, vertical, NSCORP record link
- Last touched / next action
- Signal history (list of signals with date, type, source, summary)
- Weekly AI analysis summary
- Suggested outreach (trigger type, draft email)
- Relevant NetSuite content assets (title, type, vertical tag)
- Account one-pager (generated, with regenerate and save buttons)

At the top level (dashboard view):
- Weekly digest — top accounts to contact this week, score, and reason

When the UI is done, output a proposed Supabase schema (table names, columns, types) derived from exactly what the UI needs. Check in before creating anything in Supabase.
