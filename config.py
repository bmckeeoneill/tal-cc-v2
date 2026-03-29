"""
Shared configuration helpers for TAL Command Center.
Import from here — do not duplicate in other files.
"""

import os
import re


def get_anthropic_key() -> str:
    """Return Anthropic API key from env, secrets.toml, or raise."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        content = open(secrets_path).read()
        m = re.search(r'ANTHROPIC_API_KEY\s*=\s*"([^"]+)"', content)
        if m:
            return m.group(1)
    # Streamlit runtime fallback
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    raise RuntimeError("ANTHROPIC_API_KEY not found in env, secrets.toml, or Streamlit secrets.")


REP_ID = "brianoneill"
MODEL = "claude-sonnet-4-6"
MATCH_THRESHOLD = 80
