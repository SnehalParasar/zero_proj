"""Agent 2 — Sandbox executor: Docker target + exploit script runner."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import docker

from state import SharedState
from tracing.omium import trace_agent, trace_tool

TARGET_DIR = Path(__file__).resolve().parent.parent / "target"
IMAGE_TAG = "zero-day-target:latest"
TARGET_PORT = 5001
STARTUP_WAIT_SECONDS = 3
EXPLOIT_TIMEOUT_SECONDS = 30
TARGET_URL = f"http://localhost:{TARGET_PORT}/run"


class SandboxExecutor:
    """Builds the vulnerable target container and runs exploit scripts."""

    def __init__(self, state: SharedState) -> None:
        self.state = state
        self._client: docker.DockerClient | None = None
        self._container: docker.models.containers.Container | None = None
        self._container_id: str | None = None

    def _client_or_raise(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @trace_tool("docker_start")
    def build_and_run_container(self) -> str:
        """Build image from ./target and run detached on port 5001."""
        client = self._client_or_raise()
        self.state.log_feed("Agent 2", f"Building image from {TARGET_DIR}")

        client.images.build(path=str(TARGET_DIR), tag=IMAGE_TAG, rm=True)

        self._container = client.containers.run(
            IMAGE_TAG,
            detach=True,
            ports={f"{TARGET_PORT}/tcp": TARGET_PORT},
            remove=False,
        )
        self._container_id = self._container.id
        time.sleep(STARTUP_WAIT_SECONDS)

        message = f"Container started: {self._container_id}"
        self.state.log_feed("Agent 2", message)
        self.state.sandbox_logs.append(message)
        return self._container_id

    @trace_tool("exploit_execution")
    def execute_exploit(self, exploit_code: str) -> dict[str, str | int]:
        """Write exploit to a temp file and run with Python."""
        run_id = self.state.run_id
        exploit_path = Path(tempfile.gettempdir()) / f"exploit_{run_id}.py"
        exploit_path.write_text(exploit_code, encoding="utf-8")

        self.state.log_feed("Agent 2", f"Executing exploit: {exploit_path}")
        self.state.current_exploit_code = exploit_code

        try:
            completed = subprocess.run(
                [sys.executable, str(exploit_path)],
                capture_output=True,
                text=True,
                timeout=EXPLOIT_TIMEOUT_SECONDS,
                check=False,
            )
            result: dict[str, str | int] = {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            result = {
                "stdout": exc.stdout or "",
                "stderr": (exc.stderr or "") + "\nExploit timed out after 30s",
                "returncode": -1,
            }

        log_line = (
            f"Exploit finished (code={result['returncode']}): "
            f"stdout={len(str(result['stdout']))} chars, "
            f"stderr={len(str(result['stderr']))} chars"
        )
        self.state.log_feed("Agent 2", log_line)
        self.state.sandbox_logs.append(str(result.get("stdout", "")))
        if result.get("stderr"):
            self.state.sandbox_logs.append(str(result["stderr"]))

        return result

    @trace_tool("docker_logs")
    def get_container_logs(self) -> str:
        """Fetch Docker logs for the running target container."""
        if self._container is None:
            self.state.log_feed("Agent 2", "No container — cannot fetch logs")
            return ""

        logs = self._container.logs().decode("utf-8", errors="replace")
        self.state.log_feed("Agent 2", f"Fetched container logs ({len(logs)} chars)")
        self.state.sandbox_logs.append(logs)
        return logs

    def cleanup(self) -> None:
        """Stop and remove the target container."""
        if self._container is None:
            self.state.log_feed("Agent 2", "No container to clean up")
            return

        try:
            self._container.stop(timeout=5)
        except docker.errors.APIError:
            pass

        try:
            self._container.remove(force=True)
        except docker.errors.APIError:
            pass

        self.state.log_feed("Agent 2", "Container cleaned up")
        self._container = None
        self._container_id = None


@trace_agent("sandbox_executor")
def run(state: SharedState) -> SharedState:
    """Execute sandbox phase: container lifecycle + optional exploit from state."""
    executor = SandboxExecutor(state)
    state.exploit_attempt_number += 1

    try:
        executor.build_and_run_container()

        if state.current_exploit_code.strip():
            result = executor.execute_exploit(state.current_exploit_code)
            state.exploit_success = result.get("returncode") == 0 and bool(
                str(result.get("stdout", "")).strip()
            )
        else:
            state.log_feed("Agent 2", "No exploit code in state — skipping execution")

        executor.get_container_logs()
    except docker.errors.DockerException as exc:
        state.log_feed("Agent 2", f"Docker error: {exc}")
        state.status = "failed"
    finally:
        executor.cleanup()

    return state


def _test_exploit_script() -> str:
    """Sample exploit: POST command injection payload to the vulnerable /run endpoint."""
    return f'''import json
import requests

url = "{TARGET_URL}"
payload = {{"command": "ls -la"}}
response = requests.post(url, json=payload, timeout=10)
print("status:", response.status_code)
print(json.dumps(response.json(), indent=2))
'''


if __name__ == "__main__":
    from state import SharedState

    print("=== Agent 2 Sandbox Executor — manual test ===\n")
    test_state = SharedState()
    test_state.current_exploit_code = _test_exploit_script()
    executor = SandboxExecutor(test_state)

    try:
        container_id = executor.build_and_run_container()
        print(f"Container ID: {container_id}\n")

        result = executor.execute_exploit(test_state.current_exploit_code)
        print("--- exploit stdout ---")
        print(result.get("stdout", ""))
        print("--- exploit stderr ---")
        print(result.get("stderr", ""))
        print(f"--- return code: {result.get('returncode')} ---\n")

        print("--- container logs ---")
        print(executor.get_container_logs())
    except docker.errors.DockerException as exc:
        print(f"Docker error: {exc}")
        print("Ensure Docker Desktop is running.")
    finally:
        executor.cleanup()
        print("\n=== Test complete ===")
