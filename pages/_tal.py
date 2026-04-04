"""TAL account list page."""
import streamlit as st

import db
from db import get_accounts, get_account_states, get_account_industries
from pages._shared import go, back_btn, score_badge


@st.cache_data(ttl=300)
def _cached_states():
    return get_account_states()


@st.cache_data(ttl=300)
def _cached_industries():
    return get_account_industries()


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #4A4A5A;padding-left:10px;">TAL Accounts</div>', unsafe_allow_html=True)

    col_s, col_ts, col_i, col_st = st.columns([3, 2, 2, 2])
    with col_s:
        search = st.text_input("Search company", placeholder="Company name...", label_visibility="collapsed")
    with col_ts:
        tech_search = st.text_input("Tech stack", placeholder="e.g. Odoo, QuickBooks...", label_visibility="collapsed")
    with col_i:
        all_industries = _cached_industries()
        selected_industries = st.multiselect("Industry", options=all_industries, placeholder="All industries", label_visibility="collapsed")
    with col_st:
        all_states = _cached_states()
        selected_states = st.multiselect("State", options=all_states, placeholder="All states", label_visibility="collapsed")

    if tech_search.strip():
        accounts = db.search_by_tech_stack(tech_search.strip())
        if search:
            s = search.lower()
            accounts = [a for a in accounts if s in (a.get("company_name") or "").lower()]
        if selected_states:
            accounts = [a for a in accounts if a.get("state") in selected_states]
        if selected_industries:
            accounts = [a for a in accounts if a.get("industry") in selected_industries]
    else:
        accounts = get_accounts(
            search=search or None,
            states=selected_states or None,
            industries=selected_industries or None,
        )

    # Starred filter toggle
    show_starred = st.session_state.get("show_starred_only", False)
    star_label = "Show All" if show_starred else "★ Show Starred Only"
    if st.button(star_label, key="toggle_starred_filter"):
        st.session_state["show_starred_only"] = not show_starred
        st.rerun()

    if show_starred:
        accounts = [a for a in accounts if a.get("starred")]

    st.caption(f"{len(accounts)} accounts")

    if not accounts:
        st.info("No accounts found. Try adjusting your filters.")
        return

    header_cols = st.columns([0.5, 3, 1, 1, 2, 2, 1])
    for col, h in zip(header_cols, ["", "Company", "State", "Score", "Industry", "Last Signal", "Action"]):
        col.markdown(f"**{h}**")
    st.divider()

    for acct in accounts:
        cols = st.columns([0.5, 3, 1, 1, 2, 2, 1])
        acct_id = acct["id"]
        is_starred = bool(acct.get("starred"))

        with cols[0]:
            star_icon = "★" if is_starred else "☆"
            star_style = "color:#F4B942;font-size:18px;" if is_starred else "color:#aaa;font-size:18px;"
            if st.button(star_icon, key=f"star_{acct_id}", help="Toggle priority star",
                         use_container_width=False):
                db.toggle_starred(acct_id, not is_starred)
                st.rerun()

        s = acct.get("score") or 0
        signal_date = acct.get("last_signal_date") or ""
        signal_date_str = str(signal_date)[:10] if signal_date else "—"

        with cols[1]:
            domain = acct.get("domain") or ""
            name = acct.get("company_name") or "—"
            if domain:
                st.markdown(f"**[{name}](https://{domain})**")
            else:
                st.markdown(f"**{name}**")
        with cols[2]:
            st.write(acct.get("state") or "—")
        with cols[3]:
            st.markdown(score_badge(s), unsafe_allow_html=True)
        with cols[4]:
            st.write(acct.get("industry") or "—")
        with cols[5]:
            sc = acct.get("signal_count") or 0
            st.caption(f"{sc} signals · {signal_date_str}")
        with cols[6]:
            if st.button("View", key=f"view_{acct_id}"):
                st.session_state.selected_account = acct_id
                go("account")
