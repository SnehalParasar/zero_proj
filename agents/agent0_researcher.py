"""Agent 0 — Threat Researcher: Tavily-powered battle plan generation."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from tavily import TavilyClient

from state import SharedState
from tracing.omium import trace_agent, trace_tool

load_dotenv()

PAYLOAD_HINTS = re.compile(
    r"(payload|inject|command|curl|wget|bash|python|requests\.post|/run)",
    re.IGNORECASE,
)
BYPASS_HINTS = re.compile(
    r"(bypass|filter|sanitize|encode|waf|escape|obfus|blacklist)",
    re.IGNORECASE,
)


@trace_agent("threat_researcher")
class ThreatResearcher:
    """Gathers open-source intel and compiles an exploit battle plan."""

    def __init__(self, state: SharedState, client: TavilyClient | None = None) -> None:
        self.state = state
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key and client is None:
            raise ValueError("TAVILY_API_KEY is required for ThreatResearcher")
        self._client = client or TavilyClient(api_key=api_key)

    @trace_tool("threat_research")
    def research(self, trigger: dict) -> str:
        """Search Tavily and return a structured battle plan string."""
        cve_id = (
            trigger.get("cve_id")
            or trigger.get("CVE_ID")
            or "CVE-UNKNOWN"
        )
        target_description = (
            trigger.get("description")
            or trigger.get("target_description")
            or trigger.get("target")
            or "flask-app"
        )

        query = f"{cve_id} command injection exploit technique python payload bypass 2024"
        if cve_id == "CVE-UNKNOWN" and target_description:
            query = (
                f"{target_description} command injection exploit technique "
                "python payload bypass 2024"
            )

        self.state.log_feed("Agent 0", f"Tavily search: {query[:120]}...")
        search_response = self._tavily_search(query)
        battle_plan = self._compile_battle_plan(cve_id, target_description, search_response)

        self.state.battle_plan = battle_plan
        self.state.log_feed("Agent 0", f"Battle plan created, {len(battle_plan)} chars")
        return battle_plan

    @trace_tool("tavily_search")
    def _tavily_search(self, query: str) -> dict:
        return self._client.search(query, max_results=5)

    def _compile_battle_plan(
        self,
        cve_id: str,
        target_description: str,
        search_response: dict,
    ) -> str:
        results = search_response.get("results") or []
        techniques: list[str] = []
        payloads: list[str] = []
        bypasses: list[str] = []

        for index, item in enumerate(results[:5], start=1):
            title = item.get("title", f"Finding {index}")
            snippet = (item.get("content") or "").strip().replace("\n", " ")
            snippet = snippet[:400] + ("..." if len(snippet) > 400 else "")
            techniques.append(f"- Technique {index}: {title} — {snippet}")

            if PAYLOAD_HINTS.search(snippet) or PAYLOAD_HINTS.search(title):
                payloads.append(f"- {title}: {snippet[:200]}")
            if BYPASS_HINTS.search(snippet) or BYPASS_HINTS.search(title):
                bypasses.append(f"- {title}: {snippet[:200]}")

        answer = (search_response.get("answer") or "").strip()
        if answer:
            techniques.append(f"- Technique summary: {answer[:500]}")

        if not payloads:
            payloads.append(
                '- POST JSON {"command": "<shell command>"} to http://localhost:5001/run'
            )
            payloads.append("- Python requests.post(url, json={\"command\": \"cat /etc/passwd\"})")

        if not bypasses:
            bypasses.append("- Try shell metacharacters: ; | && $(...) `command`")
            bypasses.append("- URL-encoding or nested quotes if filters are added later")

        technique_block = "\n".join(techniques) if techniques else "- Technique 1: (no results)"
        payload_block = "\n".join(payloads)
        bypass_block = "\n".join(bypasses)

        return (
            f"BATTLE PLAN for {cve_id}:\n"
            f"Target: {target_description}\n"
            f"Endpoint: POST http://localhost:5001/run (JSON command injection)\n\n"
            f"{technique_block}\n\n"
            f"Known payloads:\n{payload_block}\n\n"
            f"Bypass methods:\n{bypass_block}\n"
        )
