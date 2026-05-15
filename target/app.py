"""Intentionally vulnerable Flask target for sandbox testing."""

from __future__ import annotations

import subprocess

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.route("/run", methods=["POST"])
def run_command() -> tuple[dict[str, str], int]:
    """
    Deliberately vulnerable: executes user-supplied command via shell without sanitization.
    Body: {"command": "user input here"}
    """
    payload = request.get_json(silent=True) or {}
    cmd = payload.get("command", "")

    if not cmd:
        return {"output": "", "error": "missing command"}, 400

    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as exc:
        output = exc.output or str(exc)

    return {"output": output}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
