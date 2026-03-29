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
    resp = client.table("accounts").select("id", count="exact").eq("rep_id", rep_id).execute()
    return resp.count or 0


def init_db() -> None:
    """No-op for Supabase — schema already applied via migrations."""
    pass


def load_my_accounts() -> None:
    """No-op for Supabase — accounts loaded via load_tal.py."""
    pass


def get_account_states(rep_id: str = "brianoneill") -> list[str]:
    client = get_client()
    resp = client.table("accounts").select("state").eq("rep_id", rep_id).execute()
    return sorted(set(r["state"] for r in (resp.data or []) if r.get("state")))


def get_account_industries(rep_id: str = "brianoneill") -> list[str]:
    client = get_client()
    resp = client.table("accounts").select("industry").eq("rep_id", rep_id).execute()
    return sorted(set(r["industry"] for r in (resp.data or []) if r.get("industry")))


def get_accounts(
    rep_id: str = "brianoneill",
    search: str | None = None,
    states: list[str] | None = None,
    industries: list[str] | None = None,
) -> list[dict]:
    """Return accounts with optional filters, ordered by score desc then name."""
    client = get_client()
    q = client.table("accounts").select("*").eq("rep_id", rep_id)
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
    """Return list of {id, company_name} for all accounts."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("id, company_name")
        .eq("rep_id", rep_id)
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
    """Return signals_processed for an account in the last N days."""
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
    return resp.data or []


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


def get_account_chat_context(account_id: str) -> str:
    """Return formatted account context string for Claude chat."""
    from datetime import date, timedelta
    client = get_client()

    acct_resp = client.table("accounts").select("company_name, industry, state, city").eq("id", account_id).single().execute()
    acct = acct_resp.data or {}

    signals = get_signals_for_account(account_id, days=7)
    notes = get_notes(account_id)

    lines = [
        f"Account: {acct.get('company_name', 'Unknown')}",
        f"Industry: {acct.get('industry') or '—'} | Location: {acct.get('city') or ''}, {acct.get('state') or ''}",
    ]
    if signals:
        lines.append(f"\nRecent signals ({len(signals)} this week):")
        for s in signals[:5]:
            lines.append(f"  - [{s.get('signal_type','other')}] {s.get('headline','')}: {s.get('summary','')[:120]}")
    else:
        lines.append("\nNo signals this week.")

    if notes:
        lines.append(f"\nNotes ({len(notes)} total, most recent):")
        for n in notes[:3]:
            ts = (n.get("created_at") or "")[:10]
            lines.append(f"  - {ts}: {n.get('note_text','')[:150]}")

    return "\n".join(lines)


def get_tal_summary_context(rep_id: str = "brianoneill") -> str:
    """Return account list + upcoming events for chat context on non-account pages."""
    from datetime import date
    today = date.today().isoformat()
    client = get_client()

    accounts = client.table("accounts").select("id, company_name, industry, state, signal_count").eq("rep_id", rep_id).order("signal_count", desc=True).execute().data or []
    account_map = {a["id"]: a["company_name"] for a in accounts}

    lines = [f"TAL: {len(accounts)} accounts managed by Brian O'Neill (NetSuite ERP sales rep).\n"]
    for a in accounts[:50]:
        sc = a.get("signal_count") or 0
        lines.append(f"- {a.get('company_name')} | {a.get('industry') or 'Unknown'} | {a.get('state') or ''} | {sc} signals")
    if len(accounts) > 50:
        lines.append(f"... and {len(accounts) - 50} more accounts.")

    # Upcoming events + matched accounts
    events = client.table("events").select("id, event_name, event_date, event_type, region").gte("event_date", today).order("event_date").execute().data or []
    if events:
        lines.append(f"\nUpcoming events ({len(events)} total):")
        for e in events[:20]:
            # Get matched account names for this event
            ae_resp = client.table("account_events").select("account_id").eq("event_id", e["id"]).execute().data or []
            matched_names = [account_map.get(r["account_id"], "") for r in ae_resp if r["account_id"] in account_map]
            region = f" · {e['region']}" if e.get("region") else ""
            etype = (e.get("event_type") or "").replace("_", " ").title()
            match_str = f" → {len(matched_names)} accounts matched" if matched_names else ""
            lines.append(f"- {e.get('event_date')} | {e.get('event_name')} | {etype}{region}{match_str}")
        if len(events) > 20:
            lines.append(f"... and {len(events) - 20} more events.")
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
        .select("match_reason, events(id, event_name, event_date, event_type, region, registration_url, seismic_url)")
        .eq("account_id", account_id)
        .execute()
    )
    rows = []
    for r in (resp.data or []):
        ev = r.get("events") or {}
        if ev and ev.get("event_date", "9999") >= today:
            ev["match_reason"] = r.get("match_reason")
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
