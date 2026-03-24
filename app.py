"""TAL Command Center — Streamlit Dashboard v3."""
import streamlit as st
import datetime

st.set_page_config(
    page_title="TAL Command Center",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from db import (
    get_stats, init_db, load_my_accounts,
    get_accounts, get_account, get_account_count,
    get_account_states, get_account_industries,
)
import tal_loader
import mock_data

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
section[data-testid="stSidebar"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden !important; }

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

if not check_password():
    st.stop()

# ── Cached data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cached_stats():
    return get_stats()

@st.cache_data(ttl=300)
def cached_category_counts():
    try:
        return tal_loader.get_category_counts()
    except Exception:
        return {}

@st.cache_data(ttl=300)
def cached_account_count():
    return get_account_count()

@st.cache_data(ttl=300)
def cached_states():
    return get_account_states()

@st.cache_data(ttl=300)
def cached_industries():
    return get_account_industries()

# ── Helpers ───────────────────────────────────────────────────────────────────
TRIGGER_LABELS = {
    "exec_hire": "Exec Hire",
    "acquisition": "Acquisition/PE",
    "expansion": "Expansion",
    "outdated_system": "Legacy System",
    "ecommerce": "Ecommerce",
    "hiring_finance_exec": "Finance Hire",
}
TRIGGER_ICONS = {
    "exec_hire": "🟡",
    "acquisition": "🔴",
    "expansion": "🟢",
    "outdated_system": "⚪",
    "ecommerce": "🔵",
    "hiring_finance_exec": "🔥",
}

def go(pg: str) -> None:
    """Navigate to page via session state only — no href, no query params."""
    st.session_state.current_page = pg
    st.rerun()

def back_btn(label: str, target: str) -> None:
    st.markdown('<span class="back-btn-marker"></span>', unsafe_allow_html=True)
    if st.button(label, key=f"back_{target}"):
        go(target)

def _score_badge(score) -> str:
    score = score or 0
    cls = "score-high" if score >= 50 else "score-mid" if score >= 25 else "score-low"
    return f'<span class="score-badge {cls}">{score}</span>'

# ── HOME ──────────────────────────────────────────────────────────────────────
def render_home():
    total = cached_account_count()
    today_str = datetime.date.today().strftime("%B %-d, %Y")

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("TAL Command Center")
    st.caption(f"Brian O'Neill · Oracle NetSuite · {today_str} · {total} accounts")
    st.divider()

    # ── What's New ────────────────────────────────────────────────────────────
    st.info(
        f"📸 Screenshots: 3  ·  "
        f"📰 Articles Forwarded: 7  ·  "
        f"📣 SDR Updates: 2  ·  "
        f"💼 LinkedIn Signals: {len(mock_data.MOCK_ACTIVITY)}  ·  "
        f"📅 Events Added: {len(mock_data.MOCK_EVENTS)}"
    )

    # ── Tiles row 1 ───────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"🏢 TAL Accounts\n\n{total}\n\nactive accounts",
                     use_container_width=True, type="primary", key="tile_tal"):
            go("tal")
    with col2:
        if st.button(f"📡 Recent Activity\n\n{len(mock_data.MOCK_ACTIVITY)}\n\nsignals this week",
                     use_container_width=True, type="primary", key="tile_activity"):
            go("activity")
    with col3:
        if st.button(f"📅 Events\n\n{len(mock_data.MOCK_EVENTS)}\n\nupcoming events",
                     use_container_width=True, type="primary", key="tile_events"):
            go("events")

    # ── Tiles row 2 ───────────────────────────────────────────────────────────
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button(f"📋 TAL Changes\n\n{len(mock_data.MOCK_CHANGES)}\n\nchanges this week",
                     use_container_width=True, type="primary", key="tile_changes"):
            go("changes")
    with col5:
        if st.button(f"🎯 Best Targets\n\n{len(mock_data.MOCK_TARGETS)}\n\nhigh-priority",
                     use_container_width=True, type="primary", key="tile_targets"):
            go("targets")
    with col6:
        if st.button(f"⚡ Unmatched\n\n0\n\nno unmatched yet",
                     use_container_width=True, type="primary", key="tile_unmatched"):
            go("unmatched")

# ── TAL ───────────────────────────────────────────────────────────────────────
def render_tal():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">TAL Accounts</div>', unsafe_allow_html=True)

    col_s, col_i, col_st = st.columns([3, 2, 2])
    with col_s:
        search = st.text_input("Search company", placeholder="Company name...", label_visibility="collapsed")
    with col_i:
        all_industries = cached_industries()
        selected_industries = st.multiselect("Industry", options=all_industries, placeholder="All industries", label_visibility="collapsed")
    with col_st:
        all_states = cached_states()
        selected_states = st.multiselect("State", options=all_states, placeholder="All states", label_visibility="collapsed")

    accounts = get_accounts(
        search=search or None,
        states=selected_states or None,
        industries=selected_industries or None,
    )

    st.caption(f"{len(accounts)} accounts")

    if not accounts:
        st.info("No accounts found. Try adjusting your filters.")
        return

    header_cols = st.columns([3, 1, 1, 2, 2, 1])
    for col, h in zip(header_cols, ["Company", "State", "Score", "Industry", "Last Signal", "Action"]):
        col.markdown(f"**{h}**")
    st.divider()

    for acct in accounts:
        cols = st.columns([3, 1, 1, 2, 2, 1])
        score = acct.get("score") or 0
        signal_date = acct.get("last_signal_date") or ""
        signal_date_str = str(signal_date)[:10] if signal_date else "—"

        with cols[0]:
            domain = acct.get("domain") or ""
            name = acct.get("company_name") or "—"
            if domain:
                st.markdown(f"**[{name}](https://{domain})**")
            else:
                st.markdown(f"**{name}**")
        with cols[1]:
            st.write(acct.get("state") or "—")
        with cols[2]:
            badge_cls = "score-high" if score >= 50 else "score-mid" if score >= 25 else "score-low"
            st.markdown(
                f'<span class="score-badge {badge_cls}">{score}</span>',
                unsafe_allow_html=True,
            )
        with cols[3]:
            st.write(acct.get("industry") or "—")
        with cols[4]:
            sc = acct.get("signal_count") or 0
            st.caption(f"{sc} signals · {signal_date_str}")
        with cols[5]:
            if st.button("View", key=f"view_{acct['id']}"):
                st.session_state.selected_account = acct["id"]
                go("account")

# ── ACTIVITY ──────────────────────────────────────────────────────────────────
def render_activity():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Recent Activity</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_ACTIVITY:
        rows_html += f"""
        <tr>
            <td style="color:#667085;">{item['date']}</td>
            <td><strong>{item['company']}</strong></td>
            <td>{item['type']}</td>
            <td>{item['detail']}</td>
            <td style="color:#667085;">{item['source']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Company</th>
                <th>Type</th>
                <th>Detail</th>
                <th>Source</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

# ── EVENTS ────────────────────────────────────────────────────────────────────
def render_events():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Events</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_EVENTS:
        rows_html += f"""
        <tr>
            <td style="color:#667085;">{item['date']}</td>
            <td><strong>{item['title']}</strong></td>
            <td>{item['type']}</td>
            <td>{item['location']}</td>
            <td style="color:#667085;">{item['note']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Event</th>
                <th>Type</th>
                <th>Location</th>
                <th>Notes</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

# ── CHANGES ───────────────────────────────────────────────────────────────────
def render_changes():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">TAL Changes</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_CHANGES:
        rows_html += f"""
        <tr>
            <td style="color:#667085;">{item['date']}</td>
            <td><strong>{item['company']}</strong></td>
            <td>{item['change']}</td>
            <td style="color:#667085;">{item['reason']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Company</th>
                <th>Change</th>
                <th>Reason</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

# ── TARGETS ───────────────────────────────────────────────────────────────────
def render_targets():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Best Targets</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_TARGETS:
        badge_cls = "score-high" if item["score"] >= 50 else "score-mid" if item["score"] >= 25 else "score-low"
        rows_html += f"""
        <tr>
            <td style="color:#667085;text-align:center;">#{item['rank']}</td>
            <td><strong>{item['company']}</strong></td>
            <td>{item['state']}</td>
            <td>{item['vertical']}</td>
            <td><span class="score-badge {badge_cls}">{item['score']}</span></td>
            <td style="color:#667085;">{item['reason']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th style="text-align:center;">#</th>
                <th>Company</th>
                <th>State</th>
                <th>Vertical</th>
                <th>Score</th>
                <th>Why</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

# ── UNMATCHED ─────────────────────────────────────────────────────────────────
def render_unmatched():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Unmatched Signals</div>', unsafe_allow_html=True)
    st.info("No unmatched signals yet.")

# ── ACCOUNT ───────────────────────────────────────────────────────────────────
def render_account():
    back_btn("← Back to TAL", "tal")

    account_id = st.session_state.get("selected_account")
    if not account_id:
        st.warning("No account selected.")
        return

    acct = get_account(account_id)
    if not acct:
        st.error(f"Account {account_id} not found.")
        return

    # ── Heading ───────────────────────────────────────────────────────────────
    st.markdown(f"## {acct.get('company_name', 'Unknown')}")

    # ── Basic info ────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        for label, val in [
            ("Industry",   acct.get("industry") or "—"),
            ("State",      acct.get("state") or "—"),
            ("City",       acct.get("city") or "—"),
            ("Sales Rep",  acct.get("sales_rep") or "—"),
        ]:
            st.markdown(f'<div class="account-section-label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value">{val}</div>', unsafe_allow_html=True)
            st.write("")

    with col2:
        domain = acct.get("domain") or ""
        if domain:
            st.markdown(f'<div class="account-section-label">Website</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="https://{domain}" target="_blank">{domain}</a></div>', unsafe_allow_html=True)
            st.write("")

        li_url = acct.get("linkedin_url") or ""
        if li_url:
            st.markdown(f'<div class="account-section-label">LinkedIn</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="{li_url}" target="_blank">View Company</a></div>', unsafe_allow_html=True)
            st.write("")

        ns_url = acct.get("nscorp_url") or ""
        if ns_url:
            st.markdown(f'<div class="account-section-label">NetSuite</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="{ns_url}" target="_blank">Open in NetSuite</a></div>', unsafe_allow_html=True)
            st.write("")

    st.divider()

    # ── Placeholder sections ──────────────────────────────────────────────────
    for section in ["Signals", "Analysis", "Outreach", "Battle Card"]:
        with st.expander(section):
            st.caption("Coming in Phase 4")

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
elif page == "account":
    render_account()
else:
    render_home()
