"""Streamlit dashboard — live view of pipeline state."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# Ensure zero-day root is on sys.path when launched via `streamlit run ui/dashboard.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def fetch_state() -> dict | None:
    try:
        response = requests.get(f"{API_BASE}/state", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def main() -> None:
    st.set_page_config(page_title="Project Zero-Day", layout="wide")
    st.title("Project Zero-Day — Pipeline Dashboard")

    state = fetch_state()
    if state is None:
        st.warning(f"Cannot reach API at `{API_BASE}`. Start the server with `uvicorn main:app`.")
        if st.button("Retry"):
            st.rerun()
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Run ID", state.get("run_id", "—")[:8] + "…")
    col2.metric("Status", state.get("status", "—"))
    col3.metric("Exploit Success", "Yes" if state.get("exploit_success") else "No")

    st.subheader("Battle Plan")
    st.text_area("battle_plan", value=state.get("battle_plan", ""), height=120, disabled=True, label_visibility="collapsed")

    st.subheader("Agent Feed")
    feed = state.get("agent_feed", [])
    if feed:
        st.dataframe(feed, use_container_width=True)
    else:
        st.info("No agent activity yet.")

    st.subheader("Sandbox Logs")
    logs = state.get("sandbox_logs", [])
    st.code("\n".join(logs) if logs else "(empty)", language="text")

    st.subheader("Current Exploit")
    st.code(state.get("current_exploit_code", "") or "(empty)", language="python")

    if state.get("pr_url"):
        st.subheader("Pull Request")
        st.link_button("View PR", state["pr_url"])


if __name__ == "__main__":
    main()
