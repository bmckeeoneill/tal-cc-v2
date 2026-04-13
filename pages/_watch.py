"""Leads to Watch page."""
import datetime
import streamlit as st

import db
from pages._shared import go, back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #36677D;padding-left:10px;">👁 Leads to Watch</div>', unsafe_allow_html=True)

    leads = db.get_watch_leads()
    if not leads:
        st.info("No leads on watch. Forward a NetSuite screenshot with subject 'Watch' or 'Watch Lead' to add one.")
        return

    today = datetime.date.today()

    show_starred = st.session_state.get("watch_starred_only", False)
    if st.button("Show All" if show_starred else "★ Show Starred Only", key="watch_star_filter"):
        st.session_state["watch_starred_only"] = not show_starred
        st.rerun()

    if show_starred:
        leads = [l for l in leads if l.get("starred")]

    st.caption(f"{len(leads)} leads")

    header_cols = st.columns([0.4, 2.5, 1.2, 1.2, 2.5, 0.5, 0.8])
    for col, h in zip(header_cols, ["", "Company", "LSAD Date", "Claimable", "Notes", "★", ""]):
        col.markdown(f"**{h}**")
    st.divider()

    for lead in leads:
        lid = lead["id"]
        is_starred = bool(lead.get("starred"))
        editing_key = f"watch_edit_{lid}"

        lsad_str = str(lead.get("lsad_date") or "")[:10]
        claimable_str = "—"
        claimable_soon = False
        if lsad_str:
            try:
                lsad = datetime.date.fromisoformat(lsad_str)
                claimable = lsad + datetime.timedelta(days=30)
                days_left = (claimable - today).days
                if days_left <= 0:
                    claimable_str = "✅ Claimable now"
                    claimable_soon = True
                elif days_left <= 7:
                    claimable_str = f"⚠️ {days_left}d"
                    claimable_soon = True
                else:
                    claimable_str = f"{claimable.strftime('%b %-d')} ({days_left}d)"
            except ValueError:
                claimable_str = "—"

        cols = st.columns([0.4, 2.5, 1.2, 1.2, 2.5, 0.5, 0.8])

        with cols[0]:
            star_icon = "★" if is_starred else "☆"
            if st.button(star_icon, key=f"watch_star_{lid}", use_container_width=False):
                db.toggle_watch_starred(lid, not is_starred)
                st.rerun()

        with cols[1]:
            name = lead.get("company_name") or "Unknown"
            ns_url = lead.get("ns_url") or ""
            website = lead.get("website") or ""
            if ns_url:
                st.markdown(f"**[{name}]({ns_url})**")
            else:
                st.markdown(f"**{name}**")
            if website:
                st.caption(website)

        with cols[2]:
            st.write(lsad_str or "—")

        with cols[3]:
            if claimable_soon:
                st.markdown(f"**{claimable_str}**")
            else:
                st.write(claimable_str)

        with cols[4]:
            if st.session_state.get(editing_key):
                new_notes = st.text_area("Notes", value=lead.get("notes") or "",
                                         key=f"watch_notes_input_{lid}", height=80,
                                         label_visibility="collapsed")
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("Save", key=f"watch_save_{lid}"):
                        db.update_watch_notes(lid, new_notes)
                        st.session_state[editing_key] = False
                        st.rerun()
                with cancel_col:
                    if st.button("Cancel", key=f"watch_cancel_{lid}"):
                        st.session_state[editing_key] = False
                        st.rerun()
            else:
                notes = (lead.get("notes") or "").strip()
                if notes:
                    st.caption(notes[:200])
                if st.button("Edit", key=f"watch_edit_btn_{lid}"):
                    st.session_state[editing_key] = True
                    st.rerun()

        with cols[5]:
            st.write("")  # spacer

        with cols[6]:
            if st.button("Dismiss", key=f"watch_dismiss_{lid}"):
                db.dismiss_watch_lead(lid)
                st.rerun()

        st.divider()
