"""Docker sandbox tool — build, run, and tear down target containers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from tracing.omium import trace_tool

load_dotenv()

TARGET_DIR = Path(__file__).resolve().parent.parent / "target"


@trace_tool("docker_build")
def build_image(tag: str = "zero-day-target:latest") -> str:
    """Build the vulnerable target image. Logic to be implemented."""
    # TODO: docker.from_env(), build from TARGET_DIR/Dockerfile
    _ = tag
    return tag


@trace_tool("docker_run")
def run_container(image_tag: str = "zero-day-target:latest", port: int = 5001) -> dict:
    """Start target container and return connection metadata. Logic to be implemented."""
    # TODO: Expose port, return container id and host URL
    _ = (image_tag, port, os.getenv("DOCKER_HOST"))
    return {"container_id": "", "url": f"http://localhost:{port}"}


@trace_tool("docker_stop")
def stop_container(container_id: str) -> bool:
    """Stop and remove a running container. Logic to be implemented."""
    # TODO: container.stop(); container.remove()
    _ = container_id
    return True
