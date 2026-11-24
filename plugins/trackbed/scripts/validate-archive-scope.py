#!/usr/bin/env python3
"""Emit shared archive facts without the plan-intake checkpoint and drift gates."""

from plan_archive import archive_scope_main

if __name__ == "__main__":
    raise SystemExit(archive_scope_main())
