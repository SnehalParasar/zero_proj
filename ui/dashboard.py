"""Streamlit dashboard — live view of pipeline state."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def fetch_status(run_id: str) -> dict | None:
    try:
        response = requests.get(f"{API_BASE}/status/{run_id}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def fetch_legacy_state() -> dict | None:
    try:
        response = requests.get(f"{API_BASE}/state", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def main() -> None:
    st.set_page_config(page_title="Project Zero-Day", layout="wide")
    st.title("Project Zero-Day — Pipeline Dashboard")

    if "run_id" not in st.session_state:
        st.session_state.run_id = ""

    run_id = st.text_input(
        "Run ID (from webhook response)",
        value=st.session_state.run_id,
        placeholder="paste run_id here",
    )
    st.session_state.run_id = run_id.strip()

    auto_refresh = st.checkbox("Auto-refresh every 3s", value=True)

    if not st.session_state.run_id:
        st.info("Trigger the webhook, then paste the `run_id` from the response.")
        legacy = fetch_legacy_state()
        if legacy:
            st.session_state.run_id = legacy.get("run_id", "")
            st.rerun()
        return

    state = fetch_status(st.session_state.run_id)
    if state is None:
        st.warning(f"Cannot reach API at `{API_BASE}` or run not found.")
        if st.button("Retry"):
            st.rerun()
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Run ID", state.get("run_id", "—")[:8] + "…")
    col2.metric("Status", state.get("status", "—"))
    col3.metric("Exploit Success", "Yes" if state.get("exploit_success") else "No")

    st.subheader("Battle Plan")
    st.text_area(
        "battle_plan",
        value=state.get("battle_plan", ""),
        height=160,
        disabled=True,
        label_visibility="collapsed",
    )

    st.subheader("Agent Feed")
    feed = state.get("agent_feed", [])
    if feed:
        st.dataframe(feed, use_container_width=True)
    else:
        st.info("No agent activity yet.")

    if state.get("pr_url"):
        st.subheader("Pull Request")
        st.link_button("View PR", state["pr_url"])

    if auto_refresh and state.get("status") in ("started", "running"):
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()
