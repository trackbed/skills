#!/usr/bin/env python3
"""Compatibility entry point for plan intake validation."""

import runpy
from pathlib import Path

if __name__ == "__main__":
    validator = runpy.run_path(str(Path(__file__).resolve().parents[3] / "scripts" / "plan_archive.py"))
    raise SystemExit(validator["main"]())
