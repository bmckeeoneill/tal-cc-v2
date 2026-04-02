"""
Supabase connection and query helpers for TAL Command Center.
All queries go through this module — app.py never imports supabase directly.
"""

import streamlit as st
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Connection (cached for the session)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(account: dict) -> dict:
    """Add derived fields so Supabase rows match the shape app.py expects."""
    account["vertical"] = account.get("industry") or ""
    account.setdefault("revenue_range", None)
    account.setdefault("employees", None)
    return account


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------

def get_account_count(rep_id: str = "brianoneill") -> int:
    client = get_client()
    resp = client.table("accounts").select("id", count="exact").eq("rep_id", rep_id).eq("active", True).execute()
    return resp.count or 0


def init_db() -> None:
    """No-op for Supabase — schema already applied via migrations."""
    pass


def load_my_accounts() -> None:
    """No-op for Supabase — accounts loaded via load_tal.py."""
    pass


def get_account_states(rep_id: str = "brianoneill") -> list[str]:
    client = get_client()
    resp = client.table("accounts").select("state").eq("rep_id", rep_id).eq("active", True).execute()
    return sorted(set(r["state"] for r in (resp.data or []) if r.get("state")))


def get_account_industries(rep_id: str = "brianoneill") -> list[str]:
    client = get_client()
    resp = client.table("accounts").select("industry").eq("rep_id", rep_id).eq("active", True).execute()
    return sorted(set(r["industry"] for r in (resp.data or []) if r.get("industry")))


def get_accounts(
    rep_id: str = "brianoneill",
    search: str | None = None,
    states: list[str] | None = None,
    industries: list[str] | None = None,
) -> list[dict]:
    """Return active accounts with optional filters, ordered by score desc then name."""
    client = get_client()
    q = client.table("accounts").select("*").eq("rep_id", rep_id).eq("active", True)
    if states:
        q = q.in_("state", states)
    if industries:
        q = q.in_("industry", industries)
    resp = q.order("score", desc=True).order("company_name").execute()
    rows = resp.data or []
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r.get("company_name") or "").lower()]
    return [_normalize(r) for r in rows]


def get_account(account_id: str) -> dict | None:
    """Return a single account by UUID, or None if not found."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("*")
        .eq("id", account_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _normalize(rows[0]) if rows else None


def upsert_accounts(rows: list[dict]) -> int:
    """Insert or update accounts by zi_id + rep_id. Returns count upserted."""
    if not rows:
        return 0
    client = get_client()
    resp = (
        client.table("accounts")
        .upsert(rows, on_conflict="zi_id,rep_id")
        .execute()
    )
    return len(resp.data or [])


# ---------------------------------------------------------------------------
# Phase 4 — AI pipeline helpers
# ---------------------------------------------------------------------------

def get_unprocessed_signals(rep_id: str = "brianoneill") -> list[dict]:
    """Return all signals_raw rows where processed = false."""
    client = get_client()
    resp = (
        client.table("signals_raw")
        .select("*")
        .eq("rep_id", rep_id)
        .eq("processed", False)
        .order("created_at")
        .execute()
    )
    return resp.data or []


def get_account_names(rep_id: str = "brianoneill") -> list[dict]:
    """Return list of {id, company_name} for all active accounts."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("id, company_name")
        .eq("rep_id", rep_id)
        .eq("active", True)
        .execute()
    )
    return resp.data or []


def insert_signals_processed(row: dict) -> None:
    client = get_client()
    client.table("signals_processed").insert(row).execute()


def insert_review_queue(row: dict) -> None:
    client = get_client()
    client.table("signal_review_queue").insert(row).execute()


def get_recent_activity_count(rep_id: str = "brianoneill", days: int = 7) -> int:
    """Count of signals_processed in the last N days. Powers Recent Activity tile."""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    client = get_client()
    resp = (
        client.table("signals_processed")
        .select("id", count="exact")
        .eq("rep_id", rep_id)
        .gte("signal_date", since)
        .execute()
    )
    return resp.count or 0


def get_pending_review_count(rep_id: str = "brianoneill") -> int:
    """Count of unreviewed items in signal_review_queue. Powers Unmatched tile."""
    client = get_client()
    resp = (
        client.table("signal_review_queue")
        .select("id", count="exact")
        .eq("rep_id", rep_id)
        .eq("reviewed", False)
        .execute()
    )
    return resp.count or 0


def get_signals_for_account(account_id: str, days: int = 7) -> list[dict]:
    """Return signals_processed for an account in the last N days, deduped by raw_id."""
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    client = get_client()
    resp = (
        client.table("signals_processed")
        .select("id, raw_id, signal_type, signal_source, headline, summary, signal_date, match_confidence, file_url, source")
        .eq("account_id", account_id)
        .gte("signal_date", since)
        .order("signal_date", desc=True)
        .execute()
    )
    # Deduplicate by raw_id — keeps first (most recent) occurrence per source email
    seen_raw_ids: set = set()
    deduped = []
    for s in (resp.data or []):
        raw_id = s.get("raw_id")
        if raw_id and raw_id in seen_raw_ids:
            continue
        if raw_id:
            seen_raw_ids.add(raw_id)
        deduped.append(s)
    return deduped


def insert_weekly_analysis(row: dict) -> None:
    """Insert a new weekly analysis row. Never overwrites — unique on (account_id, week_of)."""
    client = get_client()
    client.table("weekly_analysis").insert(row).execute()


def insert_weekly_digest(rows: list[dict]) -> None:
    """Insert scored accounts for the week."""
    if not rows:
        return
    client = get_client()
    client.table("weekly_digest").upsert(rows, on_conflict="rep_id,week_of,account_id").execute()


def insert_outreach_suggestion(row: dict) -> None:
    client = get_client()
    client.table("outreach_templates").insert(row).execute()


def log_ai_call(row: dict) -> None:
    """Log a Claude API call to ai_query_log."""
    client = get_client()
    client.table("ai_query_log").insert(row).execute()


def mark_signal_processed(signal_id: str) -> None:
    client = get_client()
    client.table("signals_raw").update({"processed": True}).eq("id", signal_id).execute()


def save_note(account_id: str, note_text: str, rep_id: str = "brianoneill") -> None:
    client = get_client()
    client.table("account_notes").insert({
        "account_id": account_id,
        "rep_id": rep_id,
        "note_text": note_text.strip(),
    }).execute()


def get_notes(account_id: str) -> list[dict]:
    client = get_client()
    resp = (
        client.table("account_notes")
        .select("id, note_text, created_at")
        .eq("account_id", account_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def _build_account_block(a: dict, signals: list, notes: list, flagged_events: list) -> list[str]:
    """Format a single account into context lines. Used by both chat context functions."""
    lines = []
    lines.append(f"=== {a.get('company_name')} ===")

    loc = ", ".join(p for p in [a.get("city"), a.get("state"), a.get("zip")] if p)
    lines.append(f"Industry: {a.get('industry') or '—'} | Location: {loc or '—'} | Website: {a.get('domain') or '—'}")

    ts = a.get("tech_stack") or []
    lines.append(f"Tech stack: {', '.join(ts) if ts else '—'}")

    sdr = a.get("sdr_name")
    if sdr:
        sdr_date = (a.get("sdr_assigned_at") or "")[:10]
        briefing = (a.get("briefing_sent_at") or "")[:10]
        sdr_line = f"SDR: {sdr} (assigned {sdr_date})"
        sdr_line += f" | Briefing sent: {briefing}" if briefing else " | Briefing: not sent"
        lines.append(sdr_line)
    else:
        lines.append("SDR: not assigned")

    if signals:
        lines.append(f"Signals ({len(signals)} total):")
        for s in signals:
            lines.append(f"  [{(s.get('signal_date') or '')[:10]}] [{s.get('signal_type', '')}] {s.get('headline', '')}: {s.get('summary', '')}")
    else:
        lines.append("Signals: none")

    if notes:
        lines.append(f"Notes ({len(notes)} total):")
        for n in notes:
            lines.append(f"  [{(n.get('created_at') or '')[:10]}] {n.get('note_text', '')}")
    else:
        lines.append("Notes: none")

    if flagged_events:
        lines.append("Flagged events:")
        for ev in flagged_events:
            lines.append(f"  {ev.get('event_date', '')} | {ev.get('event_name', '')} | {(ev.get('event_type') or '').replace('_', ' ').title()} | {ev.get('registration_url') or '—'}")

    lines.append("")
    return lines


def _bulk_fetch_account_data(client, account_ids: list) -> tuple[dict, dict, dict]:
    """Bulk-fetch signals, notes, and flagged events for a list of account IDs.
    Returns (signals_by_account, notes_by_account, flagged_by_account) dicts keyed by account_id."""
    signals_by_account: dict = {}
    notes_by_account: dict = {}
    flagged_by_account: dict = {}

    if not account_ids:
        return signals_by_account, notes_by_account, flagged_by_account

    signals_raw = (
        client.table("signals_processed")
        .select("account_id, signal_type, headline, summary, signal_date")
        .in_("account_id", account_ids)
        .order("signal_date", desc=True)
        .limit(20000)
        .execute()
        .data or []
    )
    for s in signals_raw:
        signals_by_account.setdefault(s["account_id"], []).append(s)

    notes_raw = (
        client.table("account_notes")
        .select("account_id, note_text, created_at")
        .in_("account_id", account_ids)
        .order("created_at", desc=True)
        .limit(10000)
        .execute()
        .data or []
    )
    for n in notes_raw:
        notes_by_account.setdefault(n["account_id"], []).append(n)

    flagged_raw = (
        client.table("account_events")
        .select("account_id, events(event_name, event_date, event_type, registration_url)")
        .in_("account_id", account_ids)
        .eq("flagged_for_briefing", True)
        .limit(5000)
        .execute()
        .data or []
    )
    for f in flagged_raw:
        ev = f.get("events") or {}
        if ev:
            flagged_by_account.setdefault(f["account_id"], []).append(ev)

    return signals_by_account, notes_by_account, flagged_by_account


def get_account_chat_context(account_id: str) -> str:
    """Full context for one account + lightweight one-liners for all other territory accounts."""
    from datetime import date
    client = get_client()

    # Full data for the focused account
    acct_resp = client.table("accounts").select(
        "id, company_name, industry, city, state, zip, street, domain, tech_stack, "
        "sdr_name, sdr_assigned_at, briefing_sent_at, signal_count"
    ).eq("id", account_id).single().execute()
    acct = acct_resp.data or {}

    signals_by, notes_by, flagged_by = _bulk_fetch_account_data(client, [account_id])

    lines = ["## FOCUSED ACCOUNT\n"]
    lines += _build_account_block(
        acct,
        signals_by.get(account_id, []),
        notes_by.get(account_id, []),
        flagged_by.get(account_id, []),
    )

    # Lightweight one-liners for the rest of the territory
    all_accounts = (
        client.table("accounts")
        .select("id, company_name, industry, city, state, signal_count")
        .eq("rep_id", acct.get("rep_id", "brianoneill"))
        .eq("active", True)
        .neq("id", account_id)
        .order("company_name")
        .limit(1000)
        .execute()
        .data or []
    )
    lines.append(f"\n## REST OF TERRITORY ({len(all_accounts)} accounts)\n")
    for a in all_accounts:
        city_state = ", ".join(p for p in [a.get("city"), a.get("state")] if p)
        sc = a.get("signal_count") or 0
        lines.append(f"- {a.get('company_name')} | {a.get('industry') or '—'} | {city_state or '—'} | {sc} signals")

    return "\n".join(lines)


def get_tal_summary_context(rep_id: str = "brianoneill") -> str:
    """Full territory context for chat: every active account with complete signals, notes, and events."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()

    accounts = (
        client.table("accounts")
        .select(
            "id, company_name, industry, city, state, zip, domain, tech_stack, "
            "sdr_name, sdr_assigned_at, briefing_sent_at, signal_count"
        )
        .eq("rep_id", rep_id)
        .eq("active", True)
        .order("company_name")
        .limit(1000)
        .execute()
        .data or []
    )
    account_ids = [a["id"] for a in accounts]

    signals_by, notes_by, flagged_by = _bulk_fetch_account_data(client, account_ids)

    lines = [f"TAL TERRITORY — {len(accounts)} active accounts managed by Brian O'Neill (Oracle NetSuite AE).\n"]
    for a in accounts:
        aid = a["id"]
        lines += _build_account_block(
            a,
            signals_by.get(aid, []),
            notes_by.get(aid, []),
            flagged_by.get(aid, []),
        )

    # All upcoming events
    events = (
        client.table("events")
        .select("event_name, event_date, event_type, region")
        .gte("event_date", today)
        .order("event_date")
        .execute()
        .data or []
    )
    if events:
        lines.append(f"\nALL UPCOMING EVENTS ({len(events)} total):")
        for e in events:
            region = f" · {e['region']}" if e.get("region") else ""
            etype = (e.get("event_type") or "").replace("_", " ").title()
            lines.append(f"  {e.get('event_date')} | {e.get('event_name')} | {etype}{region}")
    else:
        lines.append("\nNo upcoming events in the system yet.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 5 — Events
# ---------------------------------------------------------------------------

def insert_event(row: dict) -> str | None:
    """Insert an event, skipping duplicates on event_name + event_date. Returns new id or None."""
    client = get_client()
    # Check for duplicate
    existing = (
        client.table("events")
        .select("id")
        .eq("event_name", row["event_name"])
        .eq("event_date", row["event_date"])
        .limit(1)
        .execute()
    )
    if existing.data:
        return None
    # Populate legacy 'name' column to satisfy NOT NULL constraint
    insert_row = {**row, "name": row.get("event_name", "")}
    resp = client.table("events").insert(insert_row).execute()
    rows = resp.data or []
    return rows[0]["id"] if rows else None


def get_events_for_account(account_id: str) -> list[dict]:
    """Return upcoming events matched to an account, ordered by event_date."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()
    resp = (
        client.table("account_events")
        .select("match_reason, flagged_for_briefing, events(id, event_name, event_date, event_type, region, registration_url, seismic_url)")
        .eq("account_id", account_id)
        .execute()
    )
    rows = []
    for r in (resp.data or []):
        ev = r.get("events") or {}
        if ev and ev.get("event_date", "9999") >= today:
            ev["match_reason"] = r.get("match_reason")
            ev["flagged_for_briefing"] = r.get("flagged_for_briefing") or False
            rows.append(ev)
    return sorted(rows, key=lambda x: x.get("event_date", ""))


def get_all_upcoming_events() -> list[dict]:
    """Return all upcoming events ordered by event_date."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()
    resp = (
        client.table("events")
        .select("*")
        .gte("event_date", today)
        .order("event_date")
        .execute()
    )
    return resp.data or []


def get_upcoming_event_count() -> int:
    """Count of events with event_date >= today."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()
    resp = (
        client.table("events")
        .select("id", count="exact")
        .gte("event_date", today)
        .execute()
    )
    return resp.count or 0


def get_account_full_context(account_id: str) -> dict:
    """Pull signals, events, outreach, and notes for one account (for briefing assembly)."""
    client = get_client()

    acct_resp = client.table("accounts").select("company_name, industry, state, city").eq("id", account_id).single().execute()
    acct = acct_resp.data or {}

    signals = get_signals_for_account(account_id, days=30)
    events = get_events_for_account(account_id)
    notes = get_notes(account_id)

    outreach_resp = (
        client.table("outreach_templates")
        .select("trigger_type, email_body, generated_at")
        .eq("account_id", account_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    outreach = (outreach_resp.data or [{}])[0]

    return {
        "account": acct,
        "signals": signals,
        "events": events,
        "outreach": outreach,
        "notes": notes,
    }


def upload_attachment_to_storage(file_bytes: bytes, path: str, mime_type: str = "application/octet-stream") -> str:
    """
    Upload a file to the signal-attachments bucket.
    Returns a signed URL valid for 10 years (effectively permanent for internal use).
    path should be: {rep_id}/{signal_id}/{filename}
    """
    client = get_client()
    client.storage.from_("signal-attachments").upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": mime_type, "upsert": "true"},
    )
    signed = client.storage.from_("signal-attachments").create_signed_url(path, expires_in=315360000)
    return signed["signedURL"]


# ---------------------------------------------------------------------------
# Phase 6 — Tech stack, SDR, Leads, Event invites
# ---------------------------------------------------------------------------

def update_tech_stack(account_id: str, tech_stack_list: list[str]) -> None:
    client = get_client()
    client.table("accounts").update({"tech_stack": tech_stack_list}).eq("id", account_id).execute()


def search_by_tech_stack(term: str, rep_id: str = "brianoneill") -> list[dict]:
    """Return accounts where any tech_stack element contains term (case-insensitive)."""
    client = get_client()
    resp = client.table("accounts").select("*").eq("rep_id", rep_id).execute()
    rows = resp.data or []
    term_lower = term.lower()
    return [
        _normalize(r) for r in rows
        if any(term_lower in (t or "").lower() for t in (r.get("tech_stack") or []))
    ]


def insert_event_invite(row: dict) -> None:
    client = get_client()
    client.table("event_invites").upsert(row, on_conflict="account_id,event_id").execute()


def get_event_invite(account_id: str, event_id: str) -> dict | None:
    client = get_client()
    resp = (
        client.table("event_invites")
        .select("*")
        .eq("account_id", account_id)
        .eq("event_id", event_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def flag_event_for_briefing(account_id: str, event_id: str, flagged: bool) -> None:
    client = get_client()
    client.table("account_events").update({"flagged_for_briefing": flagged}).eq("account_id", account_id).eq("event_id", event_id).execute()


def get_flagged_events(account_id: str) -> list[dict]:
    """Return flagged events for an account with invite text if available."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()
    resp = (
        client.table("account_events")
        .select("event_id, events(id, event_name, event_date, event_type, region, registration_url, seismic_url)")
        .eq("account_id", account_id)
        .eq("flagged_for_briefing", True)
        .execute()
    )
    rows = []
    for r in (resp.data or []):
        ev = r.get("events") or {}
        if not ev:
            continue
        invite = get_event_invite(account_id, ev["id"])
        ev["invite_body"] = invite.get("invite_body") if invite else None
        rows.append(ev)
    return sorted(rows, key=lambda x: x.get("event_date", ""))


def insert_lead(row: dict) -> str | None:
    client = get_client()
    resp = client.table("leads").insert(row).execute()
    rows = resp.data or []
    return rows[0]["id"] if rows else None


def get_active_leads() -> list[dict]:
    client = get_client()
    resp = (
        client.table("leads")
        .select("*")
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def dismiss_lead(lead_id: str) -> None:
    client = get_client()
    client.table("leads").update({"status": "dismissed"}).eq("id", lead_id).execute()


def get_active_lead_count() -> int:
    client = get_client()
    resp = client.table("leads").select("id", count="exact").eq("status", "active").execute()
    return resp.count or 0


def update_sdr(account_id: str, sdr_name: str) -> None:
    from datetime import datetime, timezone
    client = get_client()
    client.table("accounts").update({
        "sdr_name": sdr_name,
        "sdr_assigned_at": datetime.now(timezone.utc).isoformat(),
        "briefing_sent_at": None,
    }).eq("id", account_id).execute()


def clear_sdr(account_id: str) -> None:
    client = get_client()
    client.table("accounts").update({
        "sdr_name": None,
        "sdr_assigned_at": None,
    }).eq("id", account_id).execute()


def get_claimed_awaiting_briefing(rep_id: str = "brianoneill") -> list[dict]:
    """Accounts with SDR assigned but no briefing sent since assignment."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("id, company_name, sdr_name, sdr_assigned_at, briefing_sent_at")
        .eq("rep_id", rep_id)
        .not_.is_("sdr_name", "null")
        .order("sdr_assigned_at", desc=True)
        .execute()
    )
    rows = []
    for r in (resp.data or []):
        assigned = r.get("sdr_assigned_at") or ""
        sent = r.get("briefing_sent_at") or ""
        if not sent or sent < assigned:
            rows.append(r)
    return rows


def get_claimed_awaiting_count(rep_id: str = "brianoneill") -> int:
    return len(get_claimed_awaiting_briefing(rep_id))


def mark_briefing_sent(account_id: str) -> None:
    from datetime import datetime, timezone
    client = get_client()
    client.table("accounts").update({
        "briefing_sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", account_id).execute()


# ---------------------------------------------------------------------------
# TAL refresh helpers
# ---------------------------------------------------------------------------

def get_new_unassigned_accounts(rep_id: str = "brianoneill") -> list[dict]:
    """Active accounts not yet acknowledged after a TAL refresh."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("id, company_name, industry, state, created_at")
        .eq("rep_id", rep_id)
        .eq("active", True)
        .eq("assigned", False)
        .order("company_name")
        .execute()
    )
    return resp.data or []


def get_inactive_accounts(rep_id: str = "brianoneill") -> list[dict]:
    """Accounts marked inactive (dropped off TAL)."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("id, company_name, industry, state, updated_at")
        .eq("rep_id", rep_id)
        .eq("active", False)
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


def mark_assigned(account_id: str) -> None:
    """Mark an account as acknowledged after TAL refresh."""
    get_client().table("accounts").update({"assigned": True}).eq("id", account_id).execute()


def get_tal_changes_count(rep_id: str = "brianoneill") -> int:
    """Count for the TAL Changes tile: new unassigned + inactive accounts."""
    client = get_client()
    new_resp = client.table("accounts").select("id", count="exact").eq("rep_id", rep_id).eq("active", True).eq("assigned", False).execute()
    inactive_resp = client.table("accounts").select("id", count="exact").eq("rep_id", rep_id).eq("active", False).execute()
    return (new_resp.count or 0) + (inactive_resp.count or 0)


# ---------------------------------------------------------------------------
# Similar Customers (pgvector)
# ---------------------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    """Embed a string using OpenAI text-embedding-3-small. Returns vector as list of floats."""
    import os, re
    import openai

    # Resolve API key: env → secrets.toml → Streamlit secrets
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            content = open(secrets_path).read()
            m = re.search(r'\[openai\].*?api_key\s*=\s*"([^"]+)"', content, re.DOTALL)
            if m:
                api_key = m.group(1)
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets["openai"]["api_key"]
        except Exception:
            pass
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in env, secrets.toml [openai], or Streamlit secrets.")

    client = openai.OpenAI(api_key=api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def _scrape_website_description(domain: str, company_name: str) -> str | None:
    """Fetch a company's website and use Claude to extract a plain-English description.
    Returns description string, or None if scrape/summarization fails.
    """
    import anthropic
    import urllib.request

    if not domain:
        return None

    url = domain if domain.startswith("http") else f"https://{domain}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read(30000).decode("utf-8", errors="ignore")
    except Exception:
        # Try http if https failed
        try:
            http_url = url.replace("https://", "http://")
            req = urllib.request.Request(http_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read(30000).decode("utf-8", errors="ignore")
        except Exception:
            return None

    # Strip tags to reduce noise before sending to Claude
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:8000]

    if len(text) < 50:
        return None

    prompt = (
        f"Visit this website content for {company_name} and describe in 2-3 sentences "
        "what this company does, what they make or sell, who their customers are, and what industry they operate in. "
        "Be specific. Return only the description, nothing else.\n\n"
        f"WEBSITE CONTENT:\n{text}"
    )

    try:
        from config import get_anthropic_key, MODEL
        cl = anthropic.Anthropic(api_key=get_anthropic_key())
        resp = cl.messages.create(model=MODEL, max_tokens=256,
                                  messages=[{"role": "user", "content": prompt}])
        return resp.content[0].text.strip()
    except Exception:
        return None


def get_similar_customers(account_id: str, limit: int = 5) -> list[dict]:
    """Return top similar NetSuite customers for a given account using vector cosine similarity."""
    import datetime

    client = get_client()

    # Pull account fields
    acct_resp = client.table("accounts").select("company_name, industry, domain, tech_stack").eq("id", account_id).single().execute()
    acct = acct_resp.data or {}

    company_name = acct.get("company_name") or ""
    industry = acct.get("industry") or ""

    # Try to get a rich description from the website
    description = _scrape_website_description(acct.get("domain"), company_name)

    if description:
        query_text = description
    else:
        # Fallback: company name + industry + tech stack
        parts = [company_name]
        if industry:
            parts.append(industry)
        tech = acct.get("tech_stack")
        if tech:
            parts.append(", ".join(tech) if isinstance(tech, list) else str(tech))
        query_text = ". ".join(p for p in parts if p).strip()

    # Log scrape result
    try:
        log_ai_call({
            "rep_id": "brianoneill",
            "call_type": "similar_customers_scrape",
            "prompt_used": query_text,
            "model_version": MODEL if description else "fallback",
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except Exception:
        pass

    embedding = embed_text(query_text)

    # Log embedding call
    try:
        log_ai_call({
            "rep_id": "brianoneill",
            "call_type": "similar_customers_embedding",
            "prompt_used": query_text,
            "model_version": "text-embedding-3-small",
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except Exception:
        pass

    # Log the call
    try:
        log_ai_call({
            "rep_id": "brianoneill",
            "call_type": "similar_customers_embedding",
            "prompt_used": query_text,
            "model_version": "text-embedding-3-small",
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except Exception:
        pass

    # Fetch a larger candidate pool, then filter out TAL accounts
    resp = client.rpc("match_customers", {
        "query_embedding": embedding,
        "match_count": limit * 10,
    }).execute()
    candidates = resp.data or []

    # Load TAL account names to exclude
    tal_resp = client.table("accounts").select("company_name").eq("rep_id", "brianoneill").eq("active", True).execute()
    tal_names = {(r.get("company_name") or "").lower().strip() for r in (tal_resp.data or [])}

    from rapidfuzz import fuzz
    results = []
    for c in candidates:
        name = (c.get("company_name") or "").lower().strip()
        # Exclude if it fuzzy-matches any TAL account at 85%+
        if any(fuzz.ratio(name, t) >= 85 for t in tal_names):
            continue
        results.append(c)
        if len(results) == limit:
            break

    return results
