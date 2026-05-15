"""
Project Zero-Day — J-ROOT TERMINAL Command Center
Run: streamlit run ui/dashboard.py
Requires: uvicorn main:app running on port 8000
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
POLL_INTERVAL = 2

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #000000 !important;
    color: #00ff41 !important;
    font-family: 'Courier New', 'Share Tech Mono', monospace !important;
}
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],footer,#MainMenu {
    visibility: hidden !important; height: 0 !important;
}
body::before {
    content: ""; position: fixed; top:0;left:0;right:0;bottom:0;
    pointer-events: none; z-index: 9999;
    background: repeating-linear-gradient(
        0deg,rgba(0,0,0,0.03) 0px,rgba(0,0,0,0.03) 1px,transparent 1px,transparent 3px);
}
h1,h2,h3,h4,h5,h6,p,span,label,div,li {
    font-family: 'Courier New', monospace !important;
    color: #00ff41 !important;
}
[data-testid="stVerticalBlock"] { gap: 0.25rem; }
[data-testid="column"] { padding: 0 0.2rem !important; }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background-color: #000000 !important; color: #00ff41 !important;
    border: 1px solid #00ff41 !important; border-radius: 0 !important;
    font-family: 'Courier New', monospace !important; font-size: 0.76rem !important;
    padding: 0.25rem 0.4rem !important;
}
.stTextInput > label { color: #006622 !important; font-size: 0.65rem !important;
    font-family: 'Courier New', monospace !important; text-transform: uppercase;
    letter-spacing: 0.08em; }
[data-testid="stForm"] { border: none !important; background: transparent !important; padding: 0 !important; }

.stButton > button {
    background-color: #000000 !important; color: #00ff41 !important;
    border: 2px solid #00ff41 !important; border-radius: 0 !important;
    font-family: 'Courier New', monospace !important; font-size: 0.78rem !important;
    font-weight: bold !important; text-transform: uppercase !important;
    letter-spacing: 0.15em !important; width: 100% !important;
    padding: 0.4rem !important; transition: all 0.1s ease;
}
.stButton > button:hover {
    background-color: #00ff41 !important; color: #000000 !important;
    box-shadow: 0 0 20px #00ff41, 0 0 40px #00ff4155;
}
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #000; }
::-webkit-scrollbar-thumb { background: #00ff41; }

@keyframes pulse-green {
    0%,100% { opacity:1; text-shadow: 0 0 8px #00ff41; }
    50%      { opacity:0.5; text-shadow: none; }
}
@keyframes pulse-red {
    0%,100% { opacity:1; color:#ff3333; text-shadow: 0 0 12px #ff0000; }
    50%      { opacity:0.35; }
}
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0;} }
@keyframes redflash {
    0%   { background-color: #000000; }
    25%  { background-color: #ff000033; }
    50%  { background-color: #000000; }
    75%  { background-color: #ff000033; }
    100% { background-color: #000000; }
}
@keyframes glowgreen {
    from { text-shadow: 0 0 8px #00ff41; }
    to   { text-shadow: 0 0 24px #00ff41, 0 0 48px #00ff4188; }
}
.status-active { color:#00ff41 !important; animation: pulse-green 1.5s ease-in-out infinite; }
.status-breach { color:#ff3333 !important; animation: pulse-red 0.6s ease-in-out infinite; }
.status-standby { color:#004411 !important; }
.blink { animation: blink 1s step-end infinite; }
.glow  { color:#00ff41 !important; animation: glowgreen 0.9s ease-in-out infinite alternate; }
.red-flash { animation: redflash 0.4s ease-in-out 3; }
.compromised {
    color:#00ff41 !important; font-size:1.3rem !important;
    letter-spacing:0.2em; animation: glowgreen 0.8s ease-in-out infinite alternate;
    font-family:'Courier New',monospace !important;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Constants / helpers
# ─────────────────────────────────────────────────────────────────────────────
AGENT_COLORS: dict[str, str] = {
    "agent 0":"#00ff41","threat":"#00ff41","research":"#00ff41",
    "agent 1":"#00ffff","architect":"#00ffff",
    "agent 2":"#ffff00","sandbox":"#ffff00","executor":"#ffff00",
    "agent 3":"#ff00ff","critic":"#ff00ff",
    "github":"#66ff66","webhook":"#00ff41","pipeline":"#00ff41",
}

def _color(agent: str, message: str) -> str:
    m = message.lower()
    if any(x in m for x in ("failed","error","exhausted","neutralised","blocked","fail")):
        return "#ff3333"
    if any(x in m for x in ("success","breached","compromised","pr opened","breach")):
        return "#ffffff"
    a = agent.lower()
    for k, c in AGENT_COLORS.items():
        if k in a:
            return c
    return "#00ff41"

def _ts(raw: str) -> str:
    try:    return str(raw)[11:19]
    except: return "??:??:??"

def _panel(title: str, body: str, height: str = "auto") -> str:
    h_style = f"height:{height};overflow-y:auto;" if height != "auto" else ""
    return (
        f'<div style="border:1px solid #00ff41;background:#000;padding:0.45rem;'
        f'border-radius:0;margin-bottom:0.4rem;">'
        f'<div style="color:#00ff41;font-size:0.66rem;letter-spacing:0.14em;'
        f'border-bottom:1px solid #00ff41;margin-bottom:0.35rem;'
        f'padding-bottom:0.18rem;font-family:Courier New,monospace;">{title}</div>'
        f'<div style="{h_style}font-family:Courier New,monospace;font-size:0.72rem;">'
        f'{body}</div></div>'
    )

def _feed_line(e: dict) -> str:
    ts  = html.escape(_ts(str(e.get("timestamp",""))))
    ag  = html.escape(str(e.get("agent","SYS")).upper())
    msg = html.escape(str(e.get("message","")))
    c   = _color(str(e.get("agent","")), str(e.get("message","")))
    pfx = ""
    ml  = msg.lower()
    if any(x in ml for x in ("failed","error","neutralised","blocked")):
        pfx = '<span style="color:#ff3333">✗</span> '
    elif any(x in ml for x in ("success","breached","pr opened")):
        pfx = '<span style="color:#00ff41">✓</span> '
    return (
        f'<div style="color:{c};margin:0.06rem 0;word-break:break-word;font-size:0.7rem;">'
        f'<span style="color:#004400">C:\\&gt;</span> '
        f'<span style="color:#005511">[{ts}]</span> '
        f'<span style="font-weight:bold;color:{c}">[{ag}]</span> '
        f'<span style="color:{c}">&gt;&gt; {pfx}{msg}</span></div>'
    )

def _module_states(feed: list[dict]) -> dict[str, str]:
    states = {
        "AGENT_0":"standby","AGENT_1":"standby",
        "AGENT_2":"standby","AGENT_3":"standby",
        "DOCKER":"armed","GITHUB":"ready",
        "TAVILY":"active","OMIUM":"linked",
    }
    amap = {
        "agent 0":"AGENT_0","threat":"AGENT_0","research":"AGENT_0",
        "agent 1":"AGENT_1","architect":"AGENT_1",
        "agent 2":"AGENT_2","sandbox":"AGENT_2","executor":"AGENT_2",
        "agent 3":"AGENT_3","critic":"AGENT_3",
        "github":"GITHUB",
    }
    seen: list[str] = []
    for entry in feed:
        a = str(entry.get("agent","")).lower()
        for k, mod in amap.items():
            if k in a and (not seen or seen[-1] != mod):
                seen.append(mod)
    for mod in set(seen):
        states[mod] = "done"
    if seen:
        states[seen[-1]] = "running"
    if "AGENT_2" in set(seen):
        states["DOCKER"] = "running"
    if "GITHUB" in set(seen):
        states["GITHUB"] = "done"
    return states

def _render_mod(name: str, state: str) -> str:
    if state == "running":
        return (f'<div style="color:#00ff41;font-size:0.7rem;margin:0.1rem 0;">'
                f'<span style="animation:pulse-green 1s infinite;">▶▶▶</span> '
                f'<b>{name}</b> <span>[ACTIVE]</span></div>')
    if state == "done":
        return (f'<div style="color:#00cc33;font-size:0.7rem;margin:0.1rem 0;">'
                f'✓ {name} <span style="color:#00cc33">[DONE]</span></div>')
    if state in ("armed","active","linked","ready"):
        return (f'<div style="color:#007722;font-size:0.7rem;margin:0.1rem 0;">'
                f'· {name} <span style="color:#007722">[{state.upper()}]</span></div>')
    return (f'<div style="color:#1a4a1a;font-size:0.7rem;margin:0.1rem 0;">'
            f'· {name} <span style="color:#1a4a1a">[STANDBY]</span></div>')

def _post_webhook(cve_id: str, target: str, desc: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/webhook",
            json={"cve_id": cve_id.strip(), "target": target.strip(), "description": desc.strip()},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        st.session_state.last_error = str(exc)
        return None

def _fetch(run_id: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/status/{run_id}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="PROJECT-ZERO | TERMINAL",
        page_icon="☠", layout="wide",
        initial_sidebar_state="collapsed",
    )

    for k, v in [
        ("run_id",""),("breach_flashed",False),
        ("last_error",""),("start_time",None),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown(CSS, unsafe_allow_html=True)

    # ── Fetch state ──────────────────────────────────────────────────────────
    run_id    = st.session_state.run_id.strip()
    data      = _fetch(run_id) if run_id else None
    feed      = data.get("agent_feed", []) if data else []
    status    = data.get("status", "")     if data else ""
    exploit_ok = bool(data.get("exploit_success")) if data else False
    attempts  = data.get("exploit_attempt_number", 0) if data else 0
    pr_url    = data.get("pr_url", "")    if data else ""
    ex_code   = data.get("current_exploit_code","") if data else ""
    is_running = status in ("started","running")

    if exploit_ok and status == "success":
        sys_label, sys_cls = "BREACH",  "status-breach"
    elif is_running:
        sys_label, sys_cls = "ACTIVE",  "status-active"
    else:
        sys_label, sys_cls = "STANDBY", "status-standby"

    # ── TOP HEADER BAR ───────────────────────────────────────────────────────
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
    border-bottom:1px solid #00ff41;padding:0.3rem 0.4rem;
    background:#000;margin-bottom:0.5rem;">
  <span style="color:#00ff41;font-family:'Courier New',monospace;font-size:0.68rem;
               letter-spacing:0.12em;text-transform:uppercase;">
    PROJECT-ZERO v1.0 [ONLINE]
  </span>
  <span style="color:#00cc33;font-family:'Courier New',monospace;font-size:0.7rem;
               letter-spacing:0.18em;text-transform:uppercase;">
    ◈ MAIN CONSOLE | AUTONOMOUS RED-TEAM SWARM ◈
  </span>
  <span style="font-family:'Courier New',monospace;font-size:0.68rem;
               letter-spacing:0.1em;text-transform:uppercase;">
    SYSTEM STATUS:&nbsp;
    <span class="{sys_cls}" style="font-weight:bold;">{sys_label}</span>
  </span>
</div>
""", unsafe_allow_html=True)

    # ── THREE COLUMN LAYOUT ──────────────────────────────────────────────────
    col_l, col_m, col_r = st.columns([1.2, 2.5, 1.2], gap="small")

    # ══════════════════════════ LEFT COLUMN ═════════════════════════════════
    with col_l:
        # System modules
        mod_states = _module_states(feed)
        mods_html  = "".join(_render_mod(k, v) for k, v in mod_states.items())
        st.markdown(_panel("[ SYSTEM MODULES ]", mods_html), unsafe_allow_html=True)

        # Target scan form
        st.markdown(
            '<div style="border:1px solid #00ff41;background:#000;padding:0.45rem;'
            'border-radius:0;margin-bottom:0.4rem;">'
            '<div style="color:#00ff41;font-size:0.66rem;letter-spacing:0.14em;'
            'border-bottom:1px solid #00ff41;margin-bottom:0.35rem;'
            'padding-bottom:0.18rem;font-family:Courier New,monospace;">[ TARGET SCAN ]</div>',
            unsafe_allow_html=True,
        )
        with st.form("scan_form", clear_on_submit=False):
            cve_id = st.text_input("CVE_ID:", value="CVE-2024-1234")
            target = st.text_input("TARGET:", value="flask-app")
            desc   = st.text_input("DESC:",   value="Command injection in user input field")
            go     = st.form_submit_button("[ INITIATE SCAN ]")
        st.markdown("</div>", unsafe_allow_html=True)

        if go:
            result = _post_webhook(cve_id, target, desc)
            if result and result.get("run_id"):
                st.session_state.run_id        = result["run_id"]
                st.session_state.breach_flashed = False
                st.session_state.start_time    = time.time()
                st.session_state.last_error    = ""
                st.rerun()
            else:
                err = st.session_state.get("last_error","Connection refused")
                st.markdown(
                    f'<div style="color:#ff3333;font-size:0.68rem;'
                    f'font-family:Courier New,monospace;">✗ WEBHOOK FAIL: {html.escape(err)}</div>',
                    unsafe_allow_html=True,
                )

        # Session ID
        if run_id:
            st.markdown(
                f'<div style="border:1px dashed #00ff41;padding:0.3rem 0.4rem;'
                f'background:#000;font-size:0.62rem;font-family:Courier New,monospace;'
                f'color:#00cc33;margin-bottom:0.4rem;">'
                f'SESSION:<br/>'
                f'<span style="color:#00ff41;font-size:0.58rem;">{run_id}</span></div>',
                unsafe_allow_html=True,
            )

        # Access log — last 5
        if feed:
            log_html = "".join(
                f'<div style="color:#00aa00;font-size:0.62rem;margin:0.04rem 0;'
                f'font-family:Courier New,monospace;word-break:break-word;">'
                f'[{_ts(str(e.get("timestamp","")))}] '
                f'{html.escape(str(e.get("agent","")).upper())}: '
                f'{html.escape(str(e.get("message",""))[:55])}</div>'
                for e in feed[-5:]
            )
            st.markdown(_panel("[ ACCESS LOG ]", log_html, "110px"), unsafe_allow_html=True)

    # ══════════════════════════ MIDDLE COLUMN ═══════════════════════════════
    with col_m:
        # Red flash on first breach detection
        if exploit_ok and not st.session_state.breach_flashed:
            st.session_state.breach_flashed = True
            st.markdown(
                '<div class="red-flash" style="width:100%;border:2px solid #ff0000;'
                'padding:0.4rem;text-align:center;margin-bottom:0.4rem;">'
                '<span style="color:#ff3333;font-family:Courier New,monospace;'
                'font-size:0.8rem;letter-spacing:0.2em;">⚠ SECURITY BREACH DETECTED ⚠</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        # Main CMD history feed
        if feed:
            feed_html = "".join(_feed_line(e) for e in feed)
        else:
            feed_html = (
                '<div style="color:#005511;font-size:0.72rem;">'
                'C:\\&gt; AWAITING MISSION PARAMETERS...'
                '<span class="blink">_</span></div>'
            )

        console_body = (
            f'<div id="mc" style="height:420px;overflow-y:auto;background:#000000;'
            f'padding:0.3rem;">'
            f'{feed_html}'
            f'<div style="color:#005511;font-size:0.68rem;" class="blink">C:\\&gt; _</div>'
            f'</div>'
            f'<script>var c=document.getElementById("mc");if(c)c.scrollTop=c.scrollHeight;</script>'
        )
        st.markdown(_panel("[ MAIN CONSOLE ] CMD HISTORY", console_body), unsafe_allow_html=True)

        # Result banner
        if exploit_ok and status == "success":
            pr_btn = (
                f'<a href="{html.escape(pr_url)}" target="_blank" '
                f'style="display:inline-block;border:1px solid #00ff41;padding:0.3rem 0.8rem;'
                f'color:#00ff41;font-family:Courier New,monospace;font-size:0.68rem;'
                f'text-decoration:none;letter-spacing:0.1em;margin-top:0.4rem;">'
                f'[ PATCH DEPLOYED → VIEW PR ]</a>'
            ) if pr_url else ""
            st.markdown(
                f'<div style="border:2px solid #00ff41;background:#000;padding:0.5rem;'
                f'border-radius:0;text-align:center;margin-top:0.3rem;">'
                f'<div class="compromised">▶ TARGET COMPROMISED ◀</div>'
                f'<div style="color:#00cc33;font-family:Courier New,monospace;font-size:0.72rem;'
                f'letter-spacing:0.1em;margin:0.25rem 0;">'
                f'BREACH CONFIRMED IN <b>{attempts}</b> ATTEMPT(S)</div>'
                f'{pr_btn}</div>',
                unsafe_allow_html=True,
            )
            if ex_code.strip():
                st.code(ex_code, language="python")

        elif status == "failed":
            st.markdown(
                '<div style="border:2px solid #ff3333;background:#000;padding:0.5rem;'
                'border-radius:0;text-align:center;margin-top:0.3rem;">'
                '<div style="color:#ff3333;font-family:Courier New,monospace;font-size:1rem;'
                'letter-spacing:0.12em;text-shadow:0 0 10px #ff0000;">'
                '✗ EXPLOIT FAILED — TARGET HARDENED</div></div>',
                unsafe_allow_html=True,
            )
        elif is_running:
            st.markdown(
                '<div style="border:1px solid #004411;background:#000;padding:0.35rem;'
                'border-radius:0;text-align:center;margin-top:0.3rem;">'
                '<span style="color:#00aa00;font-family:Courier New,monospace;font-size:0.72rem;'
                'letter-spacing:0.1em;" class="blink">'
                '▶ OPERATION IN PROGRESS... STANDBY</span></div>',
                unsafe_allow_html=True,
            )

    # ══════════════════════════ RIGHT COLUMN ════════════════════════════════
    with col_r:
        # Live log — last 8
        if feed:
            live_html = "".join(
                f'<div style="color:{_color(str(e.get("agent","")),str(e.get("message","")))};"'
                f' style="font-size:0.63rem;margin:0.05rem 0;word-break:break-word;">'
                f'<span style="color:#004400;font-size:0.63rem;">[{_ts(str(e.get("timestamp","")))}]</span> '
                f'<b style="font-size:0.63rem;">{html.escape(str(e.get("agent","")).upper())}</b>: '
                f'<span style="font-size:0.63rem;">{html.escape(str(e.get("message",""))[:52])}</span></div>'
                for e in feed[-8:]
            )
        else:
            live_html = '<div style="color:#003300;font-size:0.63rem;">-- NO SIGNAL --</div>'
        st.markdown(_panel("[ LIVE LOG FEED ]", live_html, "205px"), unsafe_allow_html=True)

        # Data stream stats
        if st.session_state.start_time:
            secs = int(time.time() - st.session_state.start_time)
            elapsed = f"{secs // 60:02d}:{secs % 60:02d}"
        else:
            elapsed = "00:00"

        short_id    = (run_id[:8] + "…") if len(run_id) > 8 else (run_id or "---")
        ex_label    = "CONFIRMED" if exploit_ok else ("ACTIVE" if is_running else "PENDING")
        ex_col      = "#00ff41" if exploit_ok else ("#ffff00" if is_running else "#005511")
        st_col      = ("#ff3333" if status == "failed" else
                       "#00ff41" if status == "success" else
                       "#ffff00" if is_running else "#005511")
        pr_disp     = (
            f'<a href="{html.escape(pr_url)}" target="_blank" '
            f'style="color:#66ff66;font-size:0.62rem;text-decoration:none;">'
            f'{pr_url[:28]}…</a>' if pr_url else
            '<span style="color:#005511;">PENDING</span>'
        )

        def _row(label: str, val: str) -> str:
            return (
                f'<div style="display:flex;justify-content:space-between;'
                f'margin:0.12rem 0;font-size:0.66rem;">'
                f'<span style="color:#005511;">{label}</span>'
                f'<span style="color:#00ff41;">{val}</span></div>'
            )

        data_html = (
            _row("RUN_ID   :", f'<span style="color:#00ff41">{html.escape(short_id)}</span>') +
            _row("ATTEMPTS :", f'<span style="color:#ffff00">{attempts}/5</span>') +
            _row("STATUS   :", f'<span style="color:{st_col};font-weight:bold">{(status or "IDLE").upper()}</span>') +
            _row("RUNTIME  :", f'<span style="color:#00cc33">{elapsed}</span>') +
            _row("EXPLOIT  :", f'<span style="color:{ex_col}">{ex_label}</span>') +
            f'<div style="margin:0.12rem 0;font-size:0.66rem;">'
            f'<span style="color:#005511;">PATCH_PR :</span> {pr_disp}</div>'
        )
        st.markdown(_panel("[ DATA STREAM ]", data_html), unsafe_allow_html=True)

        # Node info footer
        st.markdown(
            f'<div style="color:#003311;font-size:0.58rem;font-family:Courier New,monospace;'
            f'margin-top:0.3rem;">NODE: {html.escape(API_BASE)} | POLL: {POLL_INTERVAL}s</div>',
            unsafe_allow_html=True,
        )

    # ── Auto-refresh ─────────────────────────────────────────────────────────
    if run_id and (data is None or status in ("started","running")):
        time.sleep(POLL_INTERVAL)
        st.rerun()


if __name__ == "__main__":
    main()
