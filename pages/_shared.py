"""Shared helpers used across page modules."""
import streamlit as st

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
    st.session_state.current_page = pg
    st.rerun()


def back_btn(label: str, target: str) -> None:
    current = st.session_state.get("current_page", "home")
    st.markdown('<span class="back-btn-marker"></span>', unsafe_allow_html=True)
    cols = st.columns([1, 1, 8])
    with cols[0]:
        if st.button(label, key=f"back_{target}_{current}"):
            go(target)
    if target != "home":
        with cols[1]:
            if st.button("🏠 Home", key=f"home_from_{target}_{current}"):
                go("home")


def score_badge(score) -> str:
    score = score or 0
    cls = "score-high" if score >= 50 else "score-mid" if score >= 25 else "score-low"
    return f'<span class="score-badge {cls}">{score}</span>'
