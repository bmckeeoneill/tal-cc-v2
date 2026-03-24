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

def fetch_accounts(rep_id: str = "brianoneill") -> list[dict]:
    """Return all accounts for a rep, ordered by company name."""
    client = get_client()
    resp = (
        client.table("accounts")
        .select("*")
        .eq("rep_id", rep_id)
        .order("company_name")
        .execute()
    )
    return [_normalize(a) for a in (resp.data or [])]


def fetch_account(account_id: str) -> dict | None:
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


def init_db() -> None:
    """No-op for Supabase — schema already applied via migrations."""
    pass


def load_my_accounts() -> None:
    """No-op for Supabase — accounts loaded via load_tal.py."""
    pass


def get_stats() -> dict:
    client = get_client()
    resp = client.table("accounts").select("id", count="exact").eq("rep_id", "brianoneill").execute()
    return {"account_count": resp.count or 0}


def get_account_count(rep_id: str = "brianoneill") -> int:
    client = get_client()
    resp = client.table("accounts").select("id", count="exact").eq("rep_id", rep_id).execute()
    return resp.count or 0


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
    """Return a single account by UUID."""
    return fetch_account(account_id)


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
