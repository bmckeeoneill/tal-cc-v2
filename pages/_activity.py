"""Recent activity page."""
from datetime import date, timedelta
import streamlit as st

import db
from pages._shared import go, back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Recent Activity</div>', unsafe_allow_html=True)

    since = (date.today() - timedelta(days=7)).isoformat()
    resp = (
        db.get_client()
        .table("signals_processed")
        .select("id, signal_date, account_id, signal_type, headline, signal_source")
        .eq("rep_id", "brianoneill")
        .gte("signal_date", since)
        .order("signal_date", desc=True)
        .execute()
    )
    signals = resp.data or []

    account_names = {a["id"]: a["company_name"] for a in db.get_account_names()}

    if not signals:
        st.info("No signals ingested in the last 7 days.")
        return

    header = st.columns([1, 2, 1, 3, 1, 1])
    for col, h in zip(header, ["Date", "Company", "Type", "Signal", "Source", ""]):
        col.markdown(f"**{h}**")
    st.divider()

    all_accounts = db.get_account_names()
    account_options = {a["company_name"]: a["id"] for a in sorted(all_accounts, key=lambda x: x["company_name"])}
    sb = db.get_client()

    for i, s in enumerate(signals):
        company = account_names.get(s.get("account_id"), "—")
        signal_type = (s.get("signal_type") or "other").replace("_", " ").title()
        sig_id = s.get("id")

        cols = st.columns([1, 2, 1, 3, 1, 1])
        cols[0].caption((s.get("signal_date") or "")[:10])
        cols[1].markdown(f"**{company}**")
        cols[2].write(signal_type)
        cols[3].write(s.get("headline") or "—")
        cols[4].caption(s.get("signal_source") or "email")
        account_id = s.get("account_id")
        if account_id and cols[5].button("View", key=f"act_view_{sig_id}"):
            st.session_state.selected_account = account_id
            go("account")

        with st.expander("Reassign to different account", expanded=False):
            selected_name = st.selectbox(
                "Account",
                options=["— select account —"] + list(account_options.keys()),
                key=f"reassign_select_{sig_id}",
                label_visibility="collapsed",
            )
            if selected_name != "— select account —":
                if st.button("Confirm reassign", key=f"reassign_confirm_{sig_id}"):
                    new_id = account_options[selected_name]
                    sb.table("signals_processed").update({"account_id": new_id}).eq("id", sig_id).execute()
                    st.rerun()
