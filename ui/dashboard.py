"""
Project Zero-Day — Hacker dashboard (API-driven).

Run with: streamlit run ui/dashboard.py
Make sure main.py (FastAPI) is running on port 8000 first.
"""

from __future__ import annotations

import html
import os
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
POLL_INTERVAL_SEC = 2

# ---------------------------------------------------------------------------
# Custom CSS — terminal / matrix aesthetic
# ---------------------------------------------------------------------------
HACKER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');

html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #0a0a0a !important;
    color: #00ff41 !important;
    font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], footer {
    visibility: hidden !important;
    height: 0 !important;
}

h1, h2, h3, h4, p, label, span, .stMarkdown, div {
    font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
    color: #00ff41 !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background-color: #0a0a0a !important;
    color: #00ff41 !important;
    border: 1px solid #00ff41 !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

.stTextInput label, .stTextArea label {
    color: #00ff41 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

div[data-testid="stForm"] {
    border: 1px solid #00ff41;
    padding: 1rem;
    border-radius: 0 !important;
    background: #050505;
}

.stButton > button {
    background-color: #0a0a0a !important;
    color: #00ff41 !important;
    border: 2px solid #00ff41 !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    width: 100%;
    transition: all 0.15s ease;
}

.stButton > button:hover {
    background-color: #00ff41 !important;
    color: #0a0a0a !important;
    box-shadow: 0 0 18px #00ff41;
}

.scanlines::before {
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    z-index: 9998;
    background: repeating-linear-gradient(
        0deg,
        rgba(0, 0, 0, 0.12) 0px,
        rgba(0, 0, 0, 0.12) 1px,
        transparent 1px,
        transparent 3px
    );
}

.blink-cursor::after {
    content: "_";
    animation: blink 1s step-end infinite;
    color: #00ff41;
}

@keyframes blink {
    50% { opacity: 0; }
}

.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: #ff0000;
    margin-right: 8px;
    animation: pulse-red 1s ease-in-out infinite;
    vertical-align: middle;
}

@keyframes pulse-red {
    0%, 100% { opacity: 1; box-shadow: 0 0 8px #ff0000; }
    50% { opacity: 0.25; box-shadow: none; }
}

.pz-header {
    border-bottom: 1px solid #00ff41;
    padding-bottom: 0.75rem;
    margin-bottom: 1rem;
}

.pz-ascii {
    color: #00ff41;
    font-size: 0.62rem;
    line-height: 1.1;
    white-space: pre;
    margin: 0;
    text-shadow: 0 0 8px rgba(0, 255, 65, 0.45);
}

.pz-subtitle {
    color: #00cc33;
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    margin-top: 0.5rem;
}

.panel-title {
    color: #00ff41;
    font-size: 0.95rem;
    letter-spacing: 0.25em;
    border-left: 3px solid #00ff41;
    padding-left: 0.6rem;
    margin-bottom: 0.75rem;
}

.feed-terminal {
    background: #050505;
    border: 1px solid #00ff41;
    height: 420px;
    overflow-y: auto;
    padding: 0.75rem;
    font-size: 0.78rem;
    line-height: 1.45;
    border-radius: 0;
}

.feed-line { margin: 0.15rem 0; word-break: break-word; }
.feed-ts { color: #008822; }
.feed-agent0, .feed-webhook, .feed-pipeline { color: #00ff41; }
.feed-agent1 { color: #00ffff; }
.feed-agent2 { color: #ffff00; }
.feed-agent3 { color: #ff00ff; }
.feed-github { color: #66ff66; }
.feed-fail { color: #ff0000; }
.feed-ok { color: #00ff41; font-weight: bold; }

.compromised {
    color: #00ff41;
    font-size: 1.6rem;
    letter-spacing: 0.15em;
    animation: glow-green 1.2s ease-in-out infinite alternate;
    text-shadow: 0 0 12px #00ff41;
}

@keyframes glow-green {
    from { opacity: 0.85; }
    to { opacity: 1; text-shadow: 0 0 22px #00ff41; }
}

.failed-header {
    color: #ff0000;
    font-size: 1.4rem;
    letter-spacing: 0.12em;
    text-shadow: 0 0 10px #ff0000;
}

.pr-link a {
    color: #00ff41 !important;
    font-size: 1rem;
    letter-spacing: 0.1em;
}

.run-id-box {
    border: 1px dashed #00ff41;
    padding: 0.5rem 0.75rem;
    margin-top: 0.75rem;
    font-size: 0.8rem;
    background: #050505;
}

code, pre {
    background: #050505 !important;
    color: #00ff41 !important;
    border: 1px solid #003311 !important;
    border-radius: 0 !important;
}
</style>
"""

ASCII_TITLE = r"""
 ██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗
 ██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝
 ██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║
 ██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║
 ██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║
 ╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝
███████╗███████╗██████╗  ██████╗     ██████╗  █████╗ ██╗   ██╗
╚══███╔╝██╔════╝██╔══██╗██╔═══██╗    ██╔══██╗██╔══██╗╚██╗ ██╔╝
  ███╔╝ █████╗  ██║  ██║██║   ██║    ██║  ██║███████║ ╚████╔╝
 ███╔╝  ██╔══╝  ██║  ██║██║   ██║    ██║  ██║██╔══██║  ╚██╔╝
███████╗███████╗██████╔╝╚██████╔╝    ██████╔╝██║  ██║   ██║
╚══════╝╚══════╝╚═════╝  ╚═════╝     ╚═════╝ ╚═╝  ╚═╝   ╚═╝
"""


def inject_css() -> None:
    st.markdown(
        f'<div class="scanlines"></div>{HACKER_CSS}',
        unsafe_allow_html=True,
    )


def post_webhook(cve_id: str, target: str, description: str) -> dict | None:
    try:
        response = requests.post(
            f"{API_BASE}/webhook",
            json={
                "cve_id": cve_id.strip(),
                "target": target.strip(),
                "description": description.strip(),
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.session_state.last_error = str(exc)
        return None


def fetch_status(run_id: str) -> dict | None:
    try:
        response = requests.get(f"{API_BASE}/status/{run_id}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def agent_color_class(agent: str, message: str) -> str:
    agent_l = agent.lower()
    msg_l = message.lower()
    if any(x in msg_l for x in ("failed", "retry", "error", "exhausted")):
        return "feed-fail"
    if any(x in msg_l for x in ("success", "succeeded", "pr opened", "compromised")):
        return "feed-ok"
    if "agent 0" in agent_l or "threat" in agent_l or "research" in agent_l:
        return "feed-agent0"
    if "agent 1" in agent_l or "architect" in agent_l:
        return "feed-agent1"
    if "agent 2" in agent_l or "sandbox" in agent_l:
        return "feed-agent2"
    if "agent 3" in agent_l or "critic" in agent_l:
        return "feed-agent3"
    if "github" in agent_l:
        return "feed-github"
    if "webhook" in agent_l:
        return "feed-webhook"
    return "feed-pipeline"


def format_feed_html(feed: list[dict]) -> str:
    if not feed:
        return '<div class="feed-line feed-agent0">&gt;&gt; AWAITING SIGNAL...</div>'

    lines: list[str] = []
    for entry in feed:
        ts = html.escape(str(entry.get("timestamp", ""))[:19])
        agent = html.escape(str(entry.get("agent", "unknown")))
        message = html.escape(str(entry.get("message", "")))
        css = agent_color_class(agent, message)

        prefix = ""
        msg_l = message.lower()
        if any(x in msg_l for x in ("failed", "retry", "error", "exhausted")):
            prefix = '<span style="color:#ff0000">✗ </span>'
        elif any(x in msg_l for x in ("success", "succeeded", "pr opened", "completed successfully")):
            prefix = '<span style="color:#00ff41">✓ </span>'

        lines.append(
            f'<div class="feed-line {css}">'
            f'<span class="feed-ts">[{ts}]</span> '
            f'<strong>[{agent}]</strong> &gt;&gt; {prefix}{message}'
            f"</div>"
        )

    lines.append(
        '<div class="feed-line feed-agent0 blink-cursor" style="margin-top:8px">'
        "&gt; _</div>"
    )
    return "\n".join(lines)


def render_header(is_running: bool) -> None:
    dot = '<span class="status-dot"></span>' if is_running else ""
    status_text = "ACTIVE" if is_running else "STANDBY"
    st.markdown(
        f"""
        <div class="pz-header scanlines">
            <pre class="pz-ascii">{ASCII_TITLE}</pre>
            <div class="pz-subtitle blink-cursor">
                {dot}AUTONOMOUS RED-TEAM SWARM | STATUS: {status_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trigger_panel() -> None:
    st.markdown('<div class="panel-title">TRIGGER PANEL</div>', unsafe_allow_html=True)

    with st.form("attack_form", clear_on_submit=False):
        cve_id = st.text_input("CVE ID", value="CVE-2024-1234")
        target = st.text_input("TARGET", value="flask-app")
        description = st.text_input(
            "DESCRIPTION",
            value="Command injection in user input field",
        )
        submitted = st.form_submit_button("INITIATE ATTACK SEQUENCE")

    if submitted:
        result = post_webhook(cve_id, target, description)
        if result and result.get("run_id"):
            st.session_state.run_id = result["run_id"]
            st.session_state.init_message = (
                f"PIPELINE INITIATED — RUN ID: {result['run_id']}"
            )
            st.session_state.last_error = ""
            st.rerun()
        else:
            err = st.session_state.get("last_error", "Unknown error")
            st.markdown(
                f'<div class="failed-header">✗ WEBHOOK FAILED: {html.escape(err)}</div>',
                unsafe_allow_html=True,
            )

    if st.session_state.get("init_message"):
        st.markdown(
            f'<div class="run-id-box">{html.escape(st.session_state.init_message)}</div>',
            unsafe_allow_html=True,
        )

    if st.session_state.get("run_id"):
        st.markdown(
            f'<div class="run-id-box">TRACKING RUN: '
            f'<span style="color:#00ffff">{html.escape(st.session_state.run_id)}</span></div>',
            unsafe_allow_html=True,
        )


def render_agent_feed(feed: list[dict]) -> None:
    st.markdown('<div class="panel-title">AGENT FEED</div>', unsafe_allow_html=True)
    feed_html = format_feed_html(feed)
    st.markdown(
        f'<div class="feed-terminal" id="agent-feed">{feed_html}</div>'
        "<script>var el=document.getElementById('agent-feed');"
        "if(el){el.scrollTop=el.scrollHeight;}</script>",
        unsafe_allow_html=True,
    )


def render_results(state: dict) -> None:
    st.markdown('<div class="panel-title">RESULTS PANEL</div>', unsafe_allow_html=True)

    status = state.get("status", "")
    exploit_ok = bool(state.get("exploit_success"))
    attempts = state.get("exploit_attempt_number", 0)
    exploit_code = state.get("current_exploit_code", "") or ""
    pr_url = state.get("pr_url", "") or ""
    feed = state.get("agent_feed", [])

    if exploit_ok and status == "success":
        st.markdown(
            '<div class="compromised">▶ TARGET COMPROMISED ◀</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="color:#00ff41">BREACH CONFIRMED IN <strong>{attempts}</strong> ATTEMPT(S)</p>',
            unsafe_allow_html=True,
        )
        if exploit_code.strip():
            st.markdown("**FINAL EXPLOIT PAYLOAD**", unsafe_allow_html=True)
            st.code(exploit_code, language="python")
        if pr_url:
            st.markdown(
                f'<p class="pr-link"><a href="{html.escape(pr_url)}" target="_blank">'
                f"PATCH DEPLOYED → VIEW PR</a></p>",
                unsafe_allow_html=True,
            )
        return

    if status == "failed":
        st.markdown(
            '<div class="failed-header">✗ EXPLOIT FAILED — MAX RETRIES REACHED</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="color:#ff0000">TOTAL ATTEMPTS: <strong>{attempts}</strong></p>',
            unsafe_allow_html=True,
        )
        st.markdown("**ATTEMPT LOG SUMMARY**", unsafe_allow_html=True)
        attempt_lines = [
            e for e in feed
            if "attempt" in str(e.get("message", "")).lower()
            or "failed" in str(e.get("message", "")).lower()
            or "retry" in str(e.get("message", "")).lower()
        ]
        if attempt_lines:
            for entry in attempt_lines[-8:]:
                agent = html.escape(str(entry.get("agent", "")))
                msg = html.escape(str(entry.get("message", "")))
                st.markdown(
                    f'<div class="feed-fail">[{agent}] &gt;&gt; {msg}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="feed-fail">&gt;&gt; NO SUCCESSFUL EXPLOITATION</div>',
                unsafe_allow_html=True,
            )
        if exploit_code.strip():
            st.markdown("**LAST EXPLOIT ATTEMPT**", unsafe_allow_html=True)
            st.code(exploit_code, language="python")
        return

    if status in ("started", "running"):
        st.markdown(
            '<div style="color:#ffff00;letter-spacing:0.1em">'
            "&gt;&gt; OPERATION IN PROGRESS... STANDBY</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="color:#008822">&gt;&gt; AWAITING ATTACK SEQUENCE</div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(
        page_title="PROJECT ZERO-DAY",
        page_icon="☠",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    if "run_id" not in st.session_state:
        st.session_state.run_id = ""
    if "init_message" not in st.session_state:
        st.session_state.init_message = ""
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""

    inject_css()

    state: dict | None = None
    run_id = st.session_state.run_id.strip()
    if run_id:
        state = fetch_status(run_id)

    is_running = bool(
        state and state.get("status") in ("started", "running")
    )
    render_header(is_running)

    if state is None and run_id:
        st.markdown(
            f'<div class="failed-header">✗ API UNREACHABLE OR RUN NOT FOUND</div>'
            f'<p style="color:#ff0000">Ensure FastAPI is running at {html.escape(API_BASE)}</p>',
            unsafe_allow_html=True,
        )

    col_left, col_right = st.columns([2, 3], gap="medium")

    with col_left:
        render_trigger_panel()

    with col_right:
        feed = state.get("agent_feed", []) if state else []
        render_agent_feed(feed)

    st.markdown("<hr style='border-color:#003311;margin:1.5rem 0'>", unsafe_allow_html=True)

    results_slot = st.empty()
    with results_slot.container():
        if state:
            render_results(state)
        else:
            render_results({"status": "", "exploit_success": False})

    st.markdown(
        f'<p style="color:#006622;font-size:0.7rem;margin-top:2rem">'
        f"NODE: {html.escape(API_BASE)} | POLL: {POLL_INTERVAL_SEC}s | "
        f"streamlit run ui/dashboard.py</p>",
        unsafe_allow_html=True,
    )

    if run_id and (state is None or state.get("status") in ("started", "running")):
        time.sleep(POLL_INTERVAL_SEC)
        st.rerun()


if __name__ == "__main__":
    main()
