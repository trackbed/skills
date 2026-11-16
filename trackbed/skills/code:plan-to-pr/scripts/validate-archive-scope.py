#!/usr/bin/env python3
"""Emit shared archive facts without the plan-intake checkpoint and drift gates."""

import runpy
from pathlib import Path


if __name__ == "__main__":
    validator = runpy.run_path(str(Path(__file__).with_name("validate-plan-state.py")))
    raise SystemExit(validator["archive_scope_main"]())
