# CLAUDE.md — TAL Command Center

## Session Start Checklist
- Read `PLANNING.md` before writing any code
- Read `tasks/todo.md` if it exists and check for open items
- Review `tasks/lessons.md` for patterns from previous sessions

---

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First** — Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan** — Check in before starting implementation
3. **Track Progress** — Mark items complete as you go
4. **Explain Changes** — High-level summary at each step
5. **Document Results** — Add review section to `tasks/todo.md`
6. **Capture Lessons** — Update `tasks/lessons.md` after corrections

---

## Core Principles

- **Simplicity First** — Make every change as simple as possible. Impact minimal code.
- **No Laziness** — Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact** — Changes should only touch what's necessary. Avoid introducing bugs.

---

## Project-Specific Rules

### Data integrity
- `signals_raw` is an append-only audit log. Never modify or delete rows after ingest.
- Never silently discard a low-confidence account match. Always write to `signal_review_queue` with a reason.
- Every table must have a `rep_id` column. No exceptions. This is what makes the system portable to other reps.

### AI output
- When generating outreach, analysis, or summaries: log the prompt used, the model version, and a timestamp alongside the output in Supabase. Output must be reproducible.
- Never overwrite a saved one-pager version. Append new versions, let the user choose which to keep.

### Signal processing
- Two-pass classification on every signal: type first, then account tagging or global fanout.
- Global events get fanned out to relevant accounts — never dropped because no single account matched.
- Fuzzy match threshold: if confidence is below 80%, route to review queue, do not auto-tag.

### Schema
- Reference `PLANNING.md` for the full table list before creating or modifying any Supabase tables.
- Run migrations as versioned files, not ad-hoc SQL.

### Email ingest
- Postmark inbound webhook, not Zapier.
- Raw payload (body + attachments as base64) goes to `signals_raw` intact.
- No processing in the receiver — just validate, timestamp, and insert.

### Context
- This project is built on top of the existing Pipeline Scout codebase and Supabase instance.
- Check Pipeline Scout's existing schema before creating new tables — reuse where it makes sense.
- TAL sync is handled by the existing Pipeline Scout ingest — confirm it works before building around it.
