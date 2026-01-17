"""Minimal Guardian mock service for local development.

Provides a /check-access endpoint compatible with the Guardian RBAC contract.
"""

# mypy: ignore-errors

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)


def _bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@app.post("/check-access")
def check_access() -> tuple[Any, int]:
    """Return a permissive authorization decision for local use."""
    deny_all = _bool_from_env("GUARDIAN_MOCK_DENY_ALL", False)
    reason = "mock-deny" if deny_all else "granted"
    payload = {
        "access_granted": not deny_all,
        "reason": reason,
    }

    if _bool_from_env("GUARDIAN_MOCK_ECHO_REQUEST", False):
        payload["request"] = request.get_json(silent=True)

    return jsonify(payload), 200


@app.get("/health")
def health() -> tuple[Any, int]:
    """Simple health check endpoint."""
    return jsonify({"status": "ok"}), 200


def main() -> None:
    """Run the mock service."""
    port = int(os.getenv("GUARDIAN_MOCK_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104


if __name__ == "__main__":
    main()
