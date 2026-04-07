"""Events drill-down page."""
import streamlit as st

import db
from pages._shared import back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #4A4A5A;padding-left:10px;">Upcoming Events</div>', unsafe_allow_html=True)

    # ── Suggested Events (unconfirmed) ────────────────────────────────────────
    suggested = db.get_suggested_events()
    if suggested:
        st.markdown(f"**{len(suggested)} Suggested — review before adding**")
        for e in suggested:
            event_id = e["id"]
            etype = (e.get("event_type") or "").replace("_", " ").title()
            region = e.get("region") or ""
            reg_link = f" · [Register]({e['registration_url']})" if e.get("registration_url") else ""
            seismic_link = f" · [Seismic]({e['seismic_url']})" if e.get("seismic_url") else ""

            cols = st.columns([4, 1, 1])
            with cols[0]:
                st.markdown(f"**{e.get('event_name','')}**")
                meta = " · ".join(p for p in [e.get("event_date",""), etype, region] if p)
                st.caption(f"{meta}{reg_link}{seismic_link}")
            with cols[1]:
                if st.button("✓ Add", key=f"confirm_ev_{event_id}", type="primary", use_container_width=True):
                    db.confirm_event(event_id)
                    st.rerun()
            with cols[2]:
                if st.button("Dismiss", key=f"dismiss_ev_{event_id}", use_container_width=True):
                    db.dismiss_event(event_id)
                    st.rerun()
        st.divider()

    # ── Confirmed upcoming events ─────────────────────────────────────────────
    events = db.get_all_upcoming_events()
    if not events:
        st.info("No upcoming events. Forward any email with 'event' in the subject to ingest.")
        return

    st.caption(f"{len(events)} upcoming events")
    rows_html = ""
    for e in events:
        reg = f'<a href="{e["registration_url"]}" target="_blank">Register</a>' if e.get("registration_url") else "—"
        seismic = f'<a href="{e["seismic_url"]}" target="_blank">Seismic</a>' if e.get("seismic_url") else "—"
        region = e.get("region") or "—"
        etype = (e.get("event_type") or "").replace("_", " ").title()
        rows_html += f"""
        <tr>
            <td style="color:#667085;">{e.get('event_date', '')}</td>
            <td><strong>{e.get('event_name', '')}</strong></td>
            <td>{etype}</td>
            <td>{region}</td>
            <td>{reg}</td>
            <td>{seismic}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th>Date</th><th>Event</th><th>Type</th><th>Region</th><th>Register</th><th>Seismic</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)
