"""Events drill-down page."""
import streamlit as st

import db
from pages._shared import back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Upcoming Events</div>', unsafe_allow_html=True)

    events = db.get_all_upcoming_events()
    if not events:
        st.info("No upcoming events. Forward an email with subject 'Events' to ingest the MMTT digest.")
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
