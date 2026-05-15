"""GitHub integration — branches, file pushes, and pull requests."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException

from state import SharedState
from tracing.omium import trace_tool

load_dotenv()

DEFAULT_PATCH_PATH = "security/patches/zero-day-fix.py"


def _repo_name() -> str:
    repo = os.getenv("GITHUB_REPO", "").strip()
    if not repo:
        raise ValueError("GITHUB_REPO is not set")
    return repo


def _github_client() -> Github:
    token = os.getenv("GITHUB_PAT", "").strip()
    if not token:
        raise ValueError("GITHUB_PAT is not set")
    return Github(token)


@trace_tool("github_branch")
def create_branch(branch_name: str) -> str:
    """Create a new branch from the repo default branch."""
    gh = _github_client()
    repo = gh.get_repo(_repo_name())
    source = repo.get_branch(repo.default_branch)
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source.commit.sha)
    return branch_name


@trace_tool("github_push")
def push_file(branch: str, path: str, content: str, message: str) -> str:
    """Create or update a file on the given branch."""
    gh = _github_client()
    repo = gh.get_repo(_repo_name())
    try:
        existing = repo.get_contents(path, ref=branch)
        repo.update_file(path, message, content, existing.sha, branch=branch)
    except GithubException:
        repo.create_file(path, message, content, branch=branch)
    return path


@trace_tool("github_pr")
def create_pull_request(branch: str, title: str, body: str) -> str:
    """Open a pull request and return its HTML URL."""
    gh = _github_client()
    repo = gh.get_repo(_repo_name())
    pr = repo.create_pull(title=title, body=body, head=branch, base=repo.default_branch)
    return pr.html_url


@trace_tool("github_open_pr")
def open_github_pr(state: SharedState) -> str:
    """
    Open a remediation PR after successful exploitation.
    Pushes patch/report content and stores URL on state.
    """
    run_id = state.run_id
    branch_name = f"zero-day/patch-{run_id[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    patch_body = state.patch_code.strip() or (
        '"""Remediation stub for command injection in POST /run."""\n\n'
        "import shlex\nimport subprocess\n\n\n"
        "def run_safe_command(command: str) -> str:\n"
        '    """Run command without shell=True; reject metacharacters."""\n'
        "    if any(c in command for c in ';|&$`<>\\n'):\n"
        '        raise ValueError("Unsafe characters in command")\n'
        "    args = shlex.split(command)\n"
        "    return subprocess.check_output(args, text=True)\n"
    )
    state.patch_code = patch_body

    report = (
        f"# Project Zero-Day — Security Report\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Timestamp: {timestamp}\n"
        f"- Status: Exploit succeeded in sandbox\n\n"
        f"## Summary\n\n"
        f"{state.battle_plan[:2000] if state.battle_plan else 'Command injection in /run endpoint.'}\n\n"
        f"## Remediation\n\n"
        f"See `{DEFAULT_PATCH_PATH}` for a safe command execution helper.\n"
    )

    state.log_feed("GitHub", f"Creating branch {branch_name}")
    create_branch(branch_name)

    push_file(
        branch_name,
        DEFAULT_PATCH_PATH,
        patch_body,
        f"fix(security): add safe command runner [{run_id[:8]}]",
    )
    push_file(
        branch_name,
        f"security/reports/{run_id}.md",
        report,
        f"docs(security): zero-day report [{run_id[:8]}]",
    )

    pr_url = create_pull_request(
        branch_name,
        f"[Zero-Day] Remediate command injection ({run_id[:8]})",
        report,
    )
    state.pr_url = pr_url
    state.log_feed("GitHub", f"Pull request opened: {pr_url}")
    return pr_url
