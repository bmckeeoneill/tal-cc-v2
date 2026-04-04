"""Contacts Added — review queue for newly extracted contacts."""
import streamlit as st

import db
from pages._shared import go, back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #36677D;padding-left:10px;">Contacts Added</div>', unsafe_allow_html=True)
    st.caption("Contacts extracted from forwarded emails. Confirm placement, then they move to the account.")

    contacts = db.get_unconfirmed_contacts()
    all_accounts = db.get_account_names()
    account_options = {a["company_name"]: a["id"] for a in sorted(all_accounts, key=lambda x: x["company_name"])}

    if not contacts:
        st.info("No contacts pending review.")
        return

    st.markdown(f"**{len(contacts)} pending confirmation**")
    st.markdown("---")

    for c in contacts:
        contact_id = c.get("id")
        company = c.get("company_name") or "—"
        name = c.get("name") or "—"
        title = c.get("title") or "—"
        email = c.get("email") or "—"
        phone = c.get("phone") or "—"
        linkedin = c.get("linkedin_url")
        cell_confirmed = c.get("cell_confirmed") or False
        account_id = c.get("account_id")

        # Header row
        hcols = st.columns([3, 2, 2, 2, 1])
        hcols[0].markdown(f"**{company}** · {name}")
        hcols[1].write(title)
        hcols[2].write(email)
        hcols[3].write(phone)
        star_label = "★ Cell" if cell_confirmed else "☆ Cell"
        if hcols[4].button(star_label, key=f"cell_{contact_id}"):
            db.toggle_cell_confirmed(str(contact_id), not cell_confirmed)
            st.rerun()

        if linkedin:
            st.markdown(f"[LinkedIn]({linkedin})")

        # Action row
        acols = st.columns([2, 2, 2, 1])
        with acols[0]:
            if st.button("✓ Confirm — right account", key=f"confirm_{contact_id}", type="primary"):
                db.confirm_contact(str(contact_id))
                st.rerun()
        with acols[1]:
            selected_name = st.selectbox(
                "Reassign to",
                options=["— reassign to —"] + list(account_options.keys()),
                key=f"creassign_{contact_id}",
                label_visibility="collapsed",
            )
        with acols[2]:
            if selected_name != "— reassign to —":
                if st.button("Reassign + Confirm", key=f"reassign_confirm_{contact_id}"):
                    new_id = account_options[selected_name]
                    db.reassign_contact(str(contact_id), new_id)
                    db.confirm_contact(str(contact_id))
                    st.rerun()
        with acols[3]:
            if st.button("Delete", key=f"cdelete_{contact_id}"):
                db.delete_contact(str(contact_id))
                st.rerun()

        st.markdown("---")
