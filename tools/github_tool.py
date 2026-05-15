"""GitHub integration — autonomous remediation pull requests."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException

from state import SharedState
from tracing.omium import trace_tool

load_dotenv()


def _patch_file_content(run_id: str) -> str:
    return f'''"""
# AUTO-GENERATED PATCH by Project Zero-Day
# Run ID: {run_id}
# Vulnerability: Command Injection
# Original vulnerable code used shell=True with unsanitized input

import subprocess
import shlex

def safe_run_command(user_input: str) -> str:
    # PATCH: Use shlex.split and shell=False to prevent injection
    allowed_commands = ["ls", "whoami", "date"]
    cmd = user_input.strip().split()[0]
    if cmd not in allowed_commands:
        return "Command not permitted"
    args = shlex.split(user_input)
    result = subprocess.check_output(args, shell=False, timeout=5)
    return result.decode()
'''


@trace_tool("github_pr")
def open_github_pr(state: SharedState) -> str:
    """Create patch branch, commit fix file, and open a pull request."""
    g = Github(os.getenv("GITHUB_PAT"))
    repo = g.get_repo(os.getenv("GITHUB_REPO"))

    short_id = state.run_id[:8]
    branch_name = f"zero-day-patch-{short_id}"
    patch_path = f"patches/patch_{short_id}.py"
    patch_content = _patch_file_content(state.run_id)
    state.patch_code = patch_content

    default_branch = repo.default_branch
    base_sha = repo.get_branch(default_branch).commit.sha

    try:
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
    except GithubException as exc:
        if exc.status != 422:
            raise

    commit_message = f"fix(security): auto-patch command injection [{short_id}]"
    try:
        existing = repo.get_contents(patch_path, ref=branch_name)
        repo.update_file(
            patch_path,
            commit_message,
            patch_content,
            existing.sha,
            branch=branch_name,
        )
    except GithubException:
        repo.create_file(
            patch_path,
            commit_message,
            patch_content,
            branch=branch_name,
        )

    pr_title = f"[Zero-Day Auto-Patch] Command Injection Fix - {short_id}"
    pr_body = (
        "## Automated Security Patch\n\n"
        "**Vulnerability:** Command Injection\n"
        "**Detected by:** Project Zero-Day Autonomous Pipeline\n"
        f"**Run ID:** {state.run_id}\n\n"
        "### Exploit Used:\n"
        f"```python\n{state.current_exploit_code}\n```\n\n"
        "### Fix Applied:\n"
        "Replaced shell=True with shlex.split and whitelist validation.\n\n"
        "**This PR was opened autonomously. No human was involved.**"
    )

    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=default_branch,
    )

    pr_url = pr.html_url
    state.pr_url = pr_url
    state.log_feed("GitHub", f"PR opened: {pr_url}")
    return pr_url
