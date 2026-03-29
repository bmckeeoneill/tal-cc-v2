"""Dashboard home page — tile grid."""
import datetime
import streamlit as st

import db
import mock_data
from pages._shared import go


def render():
    total = db.get_account_count()
    today_str = datetime.date.today().strftime("%B %-d, %Y")

    st.title("TAL Command Center")
    st.caption(f"Brian O'Neill · Oracle NetSuite · {today_str} · {total} accounts")
    st.divider()

    st.info(
        f"📸 Screenshots: 3  ·  "
        f"📰 Articles Forwarded: 7  ·  "
        f"📣 SDR Updates: 2  ·  "
        f"💼 LinkedIn Signals: {len(mock_data.MOCK_ACTIVITY)}  ·  "
        f"📅 Events Added: {len(mock_data.MOCK_EVENTS)}"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"🏢 TAL Accounts\n\n{total}\n\nactive accounts",
                     use_container_width=True, type="primary", key="tile_tal"):
            go("tal")
    with col2:
        _activity_count = db.get_recent_activity_count()
        if st.button(f"📡 Recent Activity\n\n{_activity_count}\n\nsignals this week",
                     use_container_width=True, type="primary", key="tile_activity"):
            go("activity")
    with col3:
        _event_count = db.get_upcoming_event_count()
        if st.button(f"📅 Events\n\n{_event_count}\n\nupcoming events",
                     use_container_width=True, type="primary", key="tile_events"):
            go("events")

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
        pending = db.get_pending_review_count()
        unmatched_label = f"{pending} pending" if pending else "none pending"
        if st.button(f"⚡ Unmatched\n\n{pending}\n\n{unmatched_label}",
                     use_container_width=True, type="primary", key="tile_unmatched"):
            go("unmatched")

    col7, col8, _ = st.columns(3)
    with col7:
        _lead_count = db.get_active_lead_count()
        if st.button(f"💡 Leads\n\n{_lead_count}\n\nactive leads",
                     use_container_width=True, type="primary", key="tile_leads"):
            go("leads")
    with col8:
        _claimed_count = db.get_claimed_awaiting_count()
        if st.button(f"📬 Claimed Awaiting Briefing\n\n{_claimed_count}\n\nneed briefing",
                     use_container_width=True, type="primary", key="tile_claimed"):
            go("claimed")
