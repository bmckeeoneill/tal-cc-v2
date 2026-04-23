"""Dashboard home page — tile grid."""
import datetime
import streamlit as st

import db
from pages._shared import go

_QUICK_LINKS = [
    ("Sales Navigator", "sales_navigator_url"),
    ("ZoomInfo", None, "https://www.zoominfo.com"),
    ("NSCorp", None, "https://nlcorp.app.netsuite.com"),
]


@st.cache_data(ttl=300)
def _counts():
    return {
        "accounts":       db.get_account_count(),
        "activity":       db.get_recent_activity_count(),
        "pending":        db.get_pending_review_count(),
        "starred":        db.get_starred_count(),
        "changes":        db.get_tal_changes_count(),
        "claimed":        db.get_claimed_awaiting_count(),
        "events":         db.get_upcoming_event_count(),
        "leads":          db.get_active_lead_count(),
        "contacts":       db.get_accounts_with_contacts_count(),
        "chop":           db.get_chop_block_count(),
        "watch":          db.get_watch_lead_count(),
    }


def render():
    c = _counts()
    total = c["accounts"]
    today_str = datetime.date.today().strftime("%B %-d, %Y")

    st.title("TAL Command Center")
    st.caption(f"Brian O'Neill · Oracle NetSuite · {today_str} · {total} accounts")

    # Quick Links bar
    ql_cols = st.columns(len(_QUICK_LINKS))
    secrets = st.secrets.get("external_tools", {})
    for i, link in enumerate(_QUICK_LINKS):
        label = link[0]
        url = secrets.get(link[1], "") if link[1] else link[2]
        with ql_cols[i]:
            if url:
                st.link_button(label, url, use_container_width=True)
            else:
                st.button(label, disabled=True, use_container_width=True)

    st.divider()

    # Row 1: TAL Accounts · Recent Activity · Unmatched
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"🏢 TAL Accounts\n\n{total}\n\nactive accounts",
                     use_container_width=True, type="primary", key="tile_tal"):
            go("tal")
    with col2:
        if st.button(f"📡 Recent Activity\n\n{c['activity']}\n\nsignals this week",
                     use_container_width=True, type="primary", key="tile_activity"):
            go("activity")
    with col3:
        pending = c["pending"]
        unmatched_label = f"{pending} pending" if pending else "none pending"
        if st.button(f"⚡ Unmatched\n\n{pending}\n\n{unmatched_label}",
                     use_container_width=True, type="primary", key="tile_unmatched"):
            go("unmatched")

    # Row 2: Best Targets · TAL Changes · Claimed Awaiting Briefing
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button(f"⭐ Top Targets\n\n{c['starred']}\n\nstarred accounts",
                     use_container_width=True, type="primary", key="tile_targets"):
            go("targets")
    with col5:
        if st.button(f"📋 TAL Changes\n\n{c['changes']}\n\nnew or removed",
                     use_container_width=True, type="primary", key="tile_changes"):
            go("changes")
    with col6:
        if st.button(f"📬 Claimed Awaiting Briefing\n\n{c['claimed']}\n\nneed briefing",
                     use_container_width=True, type="primary", key="tile_claimed"):
            go("claimed")

    # Row 3: Events · Leads to Check · Pipeline Scout
    col7, col8, col9 = st.columns(3)
    with col7:
        if st.button(f"📅 Events\n\n{c['events']}\n\nupcoming events",
                     use_container_width=True, type="primary", key="tile_events"):
            go("events")
    with col8:
        if st.button(f"💡 Leads to Check\n\n{c['leads']}\n\nactive leads",
                     use_container_width=True, type="primary", key="tile_leads"):
            go("leads")
    with col9:
        _ps_url = st.secrets.get("external_tools", {}).get("pipeline_scout_url", "")
        st.link_button("🔭 Pipeline Scout\n\n↗\n\nopen app",
                       _ps_url, use_container_width=True, type="primary")

    # Row 4: Contacts · Chop Block
    col10, col11, col12 = st.columns(3)
    with col10:
        if st.button(f"👤 Contacts Added\n\n{c['contacts']}\n\npending confirmation",
                     use_container_width=True, type="primary", key="tile_contacts"):
            go("contacts")
    with col11:
        if st.button(f"🪓 Chop Block\n\n{c['chop']}\n\nmarked for removal",
                     use_container_width=True, type="primary", key="tile_chop_block"):
            go("chop_block")
    with col12:
        if st.button(f"👁 Leads to Watch\n\n{c['watch']}\n\non watch list",
                     use_container_width=True, type="primary", key="tile_watch"):
            go("watch")
