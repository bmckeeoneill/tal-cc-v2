"""TAL Command Center — Streamlit entry point and router."""
import os
import datetime
import streamlit as st

st.set_page_config(
    page_title="TAL Command Center",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

import db
from db import init_db, load_my_accounts, get_account_count
from config import get_anthropic_key as _get_anthropic_key, MODEL, REP_ID
from pages._dashboard import render as render_home
from pages._tal import render as render_tal
from pages._activity import render as render_activity
from pages._events import render as render_events
from pages._misc import render_changes, render_targets
from pages._unmatched import render as render_unmatched
from pages._leads import render_leads, render_claimed
from pages._account_detail import render as render_account

# ── DB Init ───────────────────────────────────────────────────────────────────
@st.cache_resource
def _init():
    init_db()
    load_my_accounts()
    return True

_init()

# ── Navigation: read query params → session_state ─────────────────────────────
_p = st.query_params
if "page" in _p:
    st.session_state.current_page = _p["page"]
if "account" in _p:
    try:
        st.session_state.selected_account = int(_p["account"])
    except (ValueError, TypeError):
        pass

page = st.session_state.get("current_page", "home")

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Layout ── */
.block-container { padding-top: 1.5rem !important; max-width: 1280px !important; }
#MainMenu, footer, header { visibility: hidden !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── Header ── */
.scout-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0 14px 0;
    border-bottom: 2px solid #36677D;
    margin-bottom: 20px;
}
.scout-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #13212C;
    letter-spacing: -0.3px;
}
.scout-meta {
    font-size: 0.82rem;
    color: #667085;
}

/* ── Pills ── */
.pills-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 22px;
}
.pill {
    background: #E7F2F5;
    color: #36677D;
    border: 1px solid #b8d4dc;
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
    text-decoration: none;
    display: inline-block;
}
.pill:hover { background: #c8e2ea; }

/* ── Tile grid ── */
.tile-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 28px;
}
.tile {
    background: #36677D;
    color: white;
    border-radius: 12px;
    padding: 22px 24px 20px 24px;
    cursor: pointer;
    transition: opacity 0.15s, transform 0.1s;
    text-decoration: none;
    display: block;
}
.tile:hover { opacity: 0.92; transform: translateY(-1px); }
.tile.unmatched { background: #E2C06B; color: #13212C; }
.tile-header {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 14px;
}
.tile-icon { font-size: 1.3rem; }
.tile-title {
    font-size: 0.88rem;
    font-weight: 600;
    opacity: 0.88;
}
.tile.unmatched .tile-title { opacity: 0.75; }
.tile-stat {
    font-size: 3rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 5px;
}
.tile-subtitle {
    font-size: 0.78rem;
    opacity: 0.65;
    font-weight: 400;
}
.tile.unmatched .tile-subtitle { opacity: 0.6; }

/* ── Page headings ── */
.page-heading {
    font-size: 1.3rem;
    font-weight: 700;
    color: #13212C;
    margin: 0 0 20px 0;
}

/* ── Tile nav overlay button ── */
.tile { pointer-events: none; }
div[data-testid="column"]:has(.tile-nav) {
    position: relative !important;
}
div[data-testid="column"]:has(.tile-nav):hover .tile {
    opacity: 0.9;
    transform: translateY(-1px);
    transition: opacity 0.15s, transform 0.1s;
}
div[data-testid="column"]:has(.tile-nav) div[data-testid="stButton"] button {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    height: 100% !important;
    opacity: 0 !important;
    cursor: pointer !important;
    z-index: 10 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ── Pill buttons ── */
div[data-testid="column"]:has(.pill-marker) div[data-testid="stButton"] > button {
    background: #E7F2F5 !important;
    color: #36677D !important;
    border: 1px solid #b8d4dc !important;
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
}
div[data-testid="column"]:has(.pill-marker) div[data-testid="stButton"] > button:hover {
    background: #c8e2ea !important;
    border-color: #a0c4cf !important;
}

/* ── Back button (plain link style) ── */
div[data-testid="stMarkdown"]:has(.back-btn-marker) + div[data-testid="stButton"] > button {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #36677D !important;
    padding: 2px 6px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    margin-bottom: 12px !important;
}
div[data-testid="stMarkdown"]:has(.back-btn-marker) + div[data-testid="stButton"] > button:hover {
    color: #13212C !important;
    background: rgba(54, 103, 125, 0.08) !important;
}

/* ── Tables ── */
.ps-table { width: 100%; border-collapse: collapse; }
.ps-table th {
    background: #E7F2F5;
    color: #36677D;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 2px solid #c8dde4;
}
.ps-table td {
    padding: 9px 12px;
    font-size: 0.87rem;
    border-bottom: 1px solid #e8e4e0;
    color: #13212C;
    vertical-align: middle;
}
.ps-table tr:last-child td { border-bottom: none; }
.ps-table tr:hover td { background: #f5f8fa; }
.score-badge {
    display: inline-block;
    background: #36677D;
    color: white;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.8rem;
    font-weight: 700;
}
.score-high { background: #1d5c2e !important; }
.score-mid  { background: #9a6700 !important; }
.score-low  { background: #667085 !important; }

/* ── Account detail ── */
.account-section-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #667085;
    margin-bottom: 2px;
}
.account-section-value {
    font-size: 0.95rem;
    color: #13212C;
}
</style>
""", unsafe_allow_html=True)

# ── Password ──────────────────────────────────────────────────────────────────
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.markdown('<div style="max-width:380px;margin:80px auto;">', unsafe_allow_html=True)
    st.markdown("## TAL Command Center")
    st.caption("ERP buying signal detector")
    st.divider()
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Login", type="primary"):
            try:
                app_password = st.secrets.get("APP_PASSWORD", "")
            except Exception:
                app_password = ""
            if pwd == app_password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.markdown('</div>', unsafe_allow_html=True)
    return False

# Password gate disabled during development — re-enable before sharing
# if not check_password():
#     st.stop()

# ── Claude Chat Bar ───────────────────────────────────────────────────────────
import anthropic as _anthropic

CHAT_MODEL = MODEL
CHAT_SYSTEM = (
    "You are an AI assistant embedded in a NetSuite sales rep's Territory Account List tool "
    "called TAL Command Center. You help with account research, prioritization, outreach ideas, "
    "and anything else relevant to managing a sales territory.\n\n"
    "Current page context:\n{page_context}"
)


def _get_chat_context() -> str:
    if page == "account":
        account_id = st.session_state.get("selected_account")
        if account_id:
            return db.get_account_chat_context(account_id)
    return db.get_tal_summary_context()


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.form(key="chat_form", clear_on_submit=True):
    chat_cols = st.columns([8, 1, 1])
    with chat_cols[0]:
        user_input = st.text_input("Ask Claude", placeholder="Ask Claude about your accounts, signals, or outreach...",
                                   label_visibility="collapsed")
    with chat_cols[1]:
        send = st.form_submit_button("Send", use_container_width=True, type="primary")
    with chat_cols[2]:
        clear = st.form_submit_button("Clear", use_container_width=True)

if clear:
    st.session_state.chat_history = []
    st.rerun()

if send and user_input.strip():
    page_context = _get_chat_context()
    system_prompt = CHAT_SYSTEM.format(page_context=page_context)
    st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
    try:
        _client = _anthropic.Anthropic(api_key=_get_anthropic_key())
        response = _client.messages.create(
            model=CHAT_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=st.session_state.chat_history,
        )
        reply = response.content[0].text.strip()
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        db.log_ai_call({
            "rep_id": REP_ID,
            "call_type": "chat",
            "prompt_used": system_prompt,
            "model_version": CHAT_MODEL,
            "question": user_input.strip(),
            "response": reply,
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except Exception as e:
        st.error(f"Claude error: {e}")
    st.rerun()

if st.session_state.chat_history:
    last = st.session_state.chat_history[-1]
    if last["role"] == "assistant":
        st.info(last["content"])
    with st.expander("Full conversation", expanded=False):
        for msg in st.session_state.chat_history:
            role_label = "**You:**" if msg["role"] == "user" else "**Claude:**"
            st.markdown(f"{role_label} {msg['content']}")

st.markdown("---")

# ── Router ────────────────────────────────────────────────────────────────────
if page == "home":
    render_home()
elif page == "tal":
    render_tal()
elif page == "activity":
    render_activity()
elif page == "events":
    render_events()
elif page == "changes":
    render_changes()
elif page == "targets":
    render_targets()
elif page == "unmatched":
    render_unmatched()
elif page == "leads":
    render_leads()
elif page == "claimed":
    render_claimed()
elif page == "account":
    render_account()
else:
    render_home()
