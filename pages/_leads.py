"""Leads and Claimed Awaiting Briefing pages."""
import streamlit as st

import db
from pages._shared import go, back_btn


def render_leads():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Leads</div>', unsafe_allow_html=True)

    leads = db.get_active_leads()
    if not leads:
        st.info("No active leads. Forward an email or photo with subject 'Lead' to capture one.")
        return

    st.caption(f"{len(leads)} active leads")
    for lead in leads:
        c1, c2 = st.columns([5, 1])
        with c1:
            company = lead.get("company_name") or "Unknown company"
            website = lead.get("website") or ""
            date_str = (lead.get("created_at") or "")[:10]
            if website:
                st.markdown(f"**{company}** — [{website}]({website}) · {date_str}")
            else:
                st.markdown(f"**{company}** · {date_str}")
            if lead.get("file_url"):
                st.markdown(f"[📎 View image]({lead['file_url']})")
        with c2:
            if st.button("Dismiss", key=f"dismiss_lead_{lead['id']}"):
                db.dismiss_lead(lead["id"])
                st.rerun()
        st.markdown("---")


def render_claimed():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Claimed Awaiting Briefing</div>', unsafe_allow_html=True)

    accounts = db.get_claimed_awaiting_briefing()
    if not accounts:
        st.info("No accounts claimed awaiting briefing.")
        return

    st.caption(f"{len(accounts)} accounts need a briefing")
    for a in accounts:
        c1, c2 = st.columns([5, 1])
        with c1:
            assigned = (a.get("sdr_assigned_at") or "")[:10]
            st.markdown(f"**{a.get('company_name', '—')}** — SDR: {a.get('sdr_name', '—')} · Assigned {assigned}")
        with c2:
            if st.button("View", key=f"claimed_view_{a['id']}"):
                st.session_state.selected_account = a["id"]
                go("account")
        st.markdown("---")
