#!/usr/bin/env python3
"""Convenience entrypoint for poc-import CLI."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Ensure src/ is on sys.path for local execution."""
    root = Path(__file__).resolve().parent
    src_path = root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))


def _run() -> None:
    """Run the poc-import CLI after preparing sys.path."""
    _ensure_src_on_path()
    from poc_import.cli import main

    main()


if __name__ == "__main__":
    _run()
