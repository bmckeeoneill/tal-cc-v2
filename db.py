"""
Supabase connection and query helpers for TAL Command Center.
All queries go through this module — app.py never imports supabase directly.
"""

import os
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
    normalized = [_normalize(r) for r in rows]
    # Starred accounts always float to the top
    return sorted(normalized, key=lambda r: (not r.get("starred"), 0))


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
    """Count of signals_processed in the last N days, excluding dismissed."""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    client = get_client()
    resp = (
        client.table("signals_processed")
        .select("id", count="exact")
        .eq("rep_id", rep_id)
        .eq("dismissed", False)
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

    if a.get("naics_code"):
        lines.append(f"NAICS: {a['naics_code']} — {a.get('naics_description') or ''}")
    if a.get("naics_notes"):
        lines.append(f"What they do: {a['naics_notes']}")
    if a.get("naics_confidence"):
        lines.append(f"NAICS confidence: {a['naics_confidence']}")

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
        "sdr_name, sdr_assigned_at, briefing_sent_at, signal_count, "
        "naics_code, naics_description, naics_confidence, naics_notes"
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
            "sdr_name, sdr_assigned_at, briefing_sent_at, signal_count, "
            "naics_code, naics_description, naics_confidence, naics_notes"
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
        "briefing_sent_at": None,
    }).eq("id", account_id).execute()


def dismiss_signal(signal_id: str) -> None:
    """Mark a signal as dismissed — removed from activity feed but kept on account detail."""
    get_client().table("signals_processed").update({"dismissed": True}).eq("id", signal_id).execute()


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


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lead Highlights
# ---------------------------------------------------------------------------

def get_lead_highlight(account_id: str) -> str | None:
    client = get_client()
    resp = client.table("lead_highlights").select("highlight_text").eq("account_id", account_id).limit(1).execute()
    rows = resp.data or []
    return rows[0].get("highlight_text") if rows else None


def save_lead_highlight(account_id: str, text: str, rep_id: str = "brianoneill") -> None:
    from datetime import datetime, timezone
    client = get_client()
    client.table("lead_highlights").upsert({
        "account_id": account_id,
        "rep_id": rep_id,
        "highlight_text": text.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="account_id").execute()


def save_one_pager_url(account_id: str, url: str) -> None:
    get_client().table("accounts").update({"one_pager_url": url}).eq("id", account_id).execute()


def upload_one_pager(account_id: str, html: str, company_name: str) -> str:
    """Upload one pager HTML to Supabase Storage. Returns signed URL."""
    import re as _re
    # Strip anything that isn't alphanumeric, space, hyphen, or underscore
    safe = _re.sub(r"[^\w\s-]", "", company_name or "account")
    safe = _re.sub(r"[\s]+", "_", safe).strip("_") or "account"
    path = f"one-pagers/{account_id}/{safe}_one_pager.html"
    client = get_client()
    client.storage.from_("signal-attachments").upload(
        path=path,
        file=html.encode("utf-8"),
        file_options={"content-type": "text/html", "upsert": "true"},
    )
    signed = client.storage.from_("signal-attachments").create_signed_url(path, expires_in=315360000)
    url = signed["signedURL"]
    save_one_pager_url(account_id, url)
    return url


def insert_contact(row: dict) -> str | None:
    """Insert a contact row. Returns new id or None."""
    client = get_client()
    resp = client.table("contacts").insert(row).execute()
    rows = resp.data or []
    return str(rows[0]["id"]) if rows else None


def get_contacts_for_account(account_id: str) -> list[dict]:
    """Return all confirmed contacts for an account, ordered by name."""
    client = get_client()
    resp = (
        client.table("contacts")
        .select("id, name, title, email, phone, linkedin_url, cell_confirmed, created_at")
        .eq("account_id", account_id)
        .eq("confirmed", True)
        .order("name")
        .execute()
    )
    return resp.data or []


def confirm_contact(contact_id: str) -> None:
    """Mark a contact as confirmed — removes from review queue, keeps on account."""
    get_client().table("contacts").update({"confirmed": True}).eq("id", contact_id).execute()


def toggle_cell_confirmed(contact_id: str, value: bool) -> None:
    get_client().table("contacts").update({"cell_confirmed": value}).eq("id", contact_id).execute()


def reassign_contact(contact_id: str, new_account_id: str) -> None:
    """Move a contact to a different account."""
    get_client().table("contacts").update({"account_id": new_account_id}).eq("id", contact_id).execute()


def delete_contact(contact_id: str) -> None:
    get_client().table("contacts").delete().eq("id", contact_id).execute()


def get_unconfirmed_contacts(rep_id: str = "brianoneill") -> list[dict]:
    """Return unconfirmed contacts for the review queue, with account name."""
    client = get_client()
    resp = (
        client.table("contacts")
        .select("id, account_id, name, title, email, phone, linkedin_url, cell_confirmed, created_at, accounts(company_name)")
        .eq("rep_id", rep_id)
        .eq("confirmed", False)
        .order("created_at", desc=True)
        .execute()
    )
    rows = []
    for r in (resp.data or []):
        acct = r.pop("accounts", None) or {}
        r["company_name"] = acct.get("company_name") or "—"
        rows.append(r)
    return rows


def get_accounts_with_contacts_count(rep_id: str = "brianoneill") -> int:
    """Count of unconfirmed contacts pending review."""
    client = get_client()
    resp = client.table("contacts").select("id", count="exact").eq("rep_id", rep_id).eq("confirmed", False).execute()
    return resp.count or 0


def get_content_library() -> list[dict]:
    """Load content_library.json from repo root. Fresh read each call."""
    import json as _json
    path = os.path.join(os.path.dirname(__file__), "content_library.json")
    with open(path, encoding="utf-8") as f:
        return _json.load(f)


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


def get_similar_customers_naics(account_id: str, limit: int = 10, excluded_ids: list | None = None) -> list[dict]:
    """pgvector embedding similarity search — replaces random sample + Claude ranking."""
    import psycopg2
    import psycopg2.extras
    import openai as _openai
    import re as _re
    from rapidfuzz import fuzz
    from config import REP_ID

    excluded_set = set(str(i) for i in (excluded_ids or []))

    # Pull account context
    client = get_client()
    acct_resp = client.table("accounts").select(
        "company_name, industry, naics_code, naics_description, naics_notes"
    ).eq("id", account_id).single().execute()
    acct = acct_resp.data or {}

    company_name = acct.get("company_name") or ""
    industry     = acct.get("industry") or ""
    naics_code   = (acct.get("naics_code") or "").strip()
    naics_desc   = acct.get("naics_description") or ""
    naics_notes  = acct.get("naics_notes") or ""

    # TAL exclusion set (don't return accounts already in territory)
    tal_resp = client.table("accounts").select("company_name").eq("rep_id", REP_ID).eq("active", True).execute()
    tal_names = {(r.get("company_name") or "").lower().strip() for r in (tal_resp.data or [])}

    # Generate embedding for this account
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    oa_key = None
    try:
        import streamlit as _st
        oa_key = _st.secrets.get("openai", {}).get("api_key")
    except Exception:
        pass
    if not oa_key and os.path.exists(secrets_path):
        content = open(secrets_path).read()
        m = _re.search(r'\[openai\].*?api_key\s*=\s*"([^"]+)"', content, _re.DOTALL)
        if m:
            oa_key = m.group(1)
    if not oa_key:
        return []

    embed_text = f"{company_name} | {naics_code} {naics_desc} | {industry} | {naics_notes}"
    oa = _openai.OpenAI(api_key=oa_key)
    emb_resp = oa.embeddings.create(model="text-embedding-3-small", input=[embed_text])
    emb = emb_resp.data[0].embedding
    emb_str = "[" + ",".join(str(x) for x in emb) + "]"

    # pgvector similarity search — fetch limit*4 candidates to allow filtering
    fetch_n = max(limit * 4, 40)
    secrets_content = open(secrets_path).read() if os.path.exists(secrets_path) else ""
    db_m = _re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', secrets_content)
    if not db_m:
        return []

    conn = psycopg2.connect(db_m.group(1))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, company_name, website, industry, business_type, naics_code,
               naics_description, reference_status, state, v_rank, highlights,
               references_descriptors,
               1 - (embedding <=> %s::vector) AS similarity
        FROM customers
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb_str, emb_str, fetch_n))
    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        cid = str(row["id"])
        if cid in excluded_set:
            continue
        name = (row["company_name"] or "").lower().strip()
        if any(fuzz.ratio(name, t) >= 85 for t in tal_names):
            continue
        results.append(dict(row))
        if len(results) >= limit:
            break

    return results


def lock_customer(account_id: str, customer_id: str, rep_id: str = "brianoneill") -> None:
    """Lock a customer as a reference match for this account."""
    get_client().table("account_customers").upsert(
        {"account_id": account_id, "customer_id": customer_id, "rep_id": rep_id, "status": "locked"},
        on_conflict="account_id,customer_id",
    ).execute()


def dismiss_customer(account_id: str, customer_id: str, rep_id: str = "brianoneill") -> None:
    """Dismiss a customer so it never shows for this account again."""
    get_client().table("account_customers").upsert(
        {"account_id": account_id, "customer_id": customer_id, "rep_id": rep_id, "status": "dismissed"},
        on_conflict="account_id,customer_id",
    ).execute()


def get_locked_customers(account_id: str) -> list[dict]:
    """Return all locked customers for an account with full customer details."""
    client = get_client()
    ac_resp = client.table("account_customers").select("customer_id") \
        .eq("account_id", account_id).eq("status", "locked").execute()
    ids = [r["customer_id"] for r in (ac_resp.data or [])]
    if not ids:
        return []
    cust_resp = client.table("customers").select("id, company_name, website, industry, notes") \
        .in_("id", ids).execute()
    return cust_resp.data or []


def get_dismissed_customer_ids(account_id: str) -> list[str]:
    """Return list of dismissed customer UUIDs for an account."""
    resp = get_client().table("account_customers").select("customer_id") \
        .eq("account_id", account_id).eq("status", "dismissed").execute()
    return [r["customer_id"] for r in (resp.data or [])]


def search_customers(term: str, excluded_ids: list[str] | None = None, limit: int = 20) -> list[dict]:
    """Full-table keyword search across customer name/industry/what_they_do/naics/business_model."""
    if not term or not term.strip():
        return []
    t = term.strip().lower()
    resp = get_client().table("customers").select(
        "id, company_name, website, industry, sub_industry, what_they_do, naics_description, business_model, reference_status"
    ).or_(
        f"company_name.ilike.%{t}%,"
        f"industry.ilike.%{t}%,"
        f"what_they_do.ilike.%{t}%,"
        f"naics_description.ilike.%{t}%,"
        f"business_model.ilike.%{t}%"
    ).limit(limit + len(excluded_ids or [])).execute()

    rows = resp.data or []
    if excluded_ids:
        excl = set(str(x) for x in excluded_ids)
        rows = [r for r in rows if str(r["id"]) not in excl]
    return rows[:limit]


def get_starred_count() -> int:
    from config import REP_ID as _REP_ID
    resp = get_client().table("accounts").select("id", count="exact") \
        .eq("rep_id", _REP_ID).eq("active", True).eq("starred", True).execute()
    return resp.count or 0


def get_starred_accounts() -> list[dict]:
    from config import REP_ID as _REP_ID
    resp = get_client().table("accounts") \
        .select("id, company_name, industry, state, revenue_range, domain, signal_count, last_signal_date") \
        .eq("rep_id", _REP_ID).eq("active", True).eq("starred", True) \
        .order("company_name").execute()
    return resp.data or []


def get_account_by_ns_id(ns_id: str) -> dict | None:
    """Look up an account by its NetSuite custjob record ID embedded in nscorp_url."""
    resp = get_client().table("accounts").select("id, company_name") \
        .ilike("nscorp_url", f"%id={ns_id}%").eq("active", True).limit(1).execute()
    return (resp.data or [None])[0]


def toggle_starred(account_id: str, starred: bool) -> None:
    """Set starred flag on an account."""
    get_client().table("accounts").update({"starred": starred}).eq("id", account_id).execute()


_OUTREACH_DEFAULT = """You are a NetSuite sales rep writing a short outreach email.

Account: {account_name}
Industry: {industry}
NAICS: {naics_description}
What they do: {naics_notes}
Tech stack: {tech_stack}
Recent signals: {signal_summaries}

Write a short outreach email following this structure:
1. Industry-specific hook: one sentence. Something specific and a little absurd that shows you understand their world. Written like something a rep heard in the field, not a case study.
2. Signal or trigger reference: one sentence. Why you are reaching out right now.
3. CTA: direct and cheeky. Examples: "Is this something you are thinking about?" or "Let me know if this is a project you might be looking at in the next year or two."

Tone rules — no exceptions:
- No em dashes
- No hyphens used as dashes between phrases
- No hyphenated words
- No complex or formal vocabulary
- Short sentences only
- Sounds like a human wrote it quickly
- A little cheeky is fine
- No filler words
- No bold font

Length: two sentences plus a CTA. That is it."""


def get_outreach_prompt(rep_id: str = "brianoneill") -> str:
    """Return stored prompt template or the default."""
    resp = get_client().table("outreach_config").select("prompt_template") \
        .eq("rep_id", rep_id).limit(1).execute()
    rows = resp.data or []
    return rows[0]["prompt_template"] if rows else _OUTREACH_DEFAULT


def save_outreach_prompt(rep_id: str, template: str) -> None:
    """Upsert prompt template for a rep."""
    import datetime
    get_client().table("outreach_config").upsert(
        {"rep_id": rep_id, "prompt_template": template,
         "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
        on_conflict="rep_id",
    ).execute()
