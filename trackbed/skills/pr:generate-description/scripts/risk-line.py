#!/usr/bin/env python3
"""Generate or check the deterministic risk line in a Pull Request description."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

RISK_SIGNALS = Path(__file__).resolve().parents[3] / "scripts" / "risk-signals.py"


def policy_ref() -> str:
    origin_head = "refs/remotes/origin/HEAD"
    if subprocess.run(["git", "symbolic-ref", "--quiet", origin_head], stdout=subprocess.DEVNULL).returncode == 0:
        return origin_head
    for ref in ("refs/remotes/origin/main", "refs/remotes/origin/master"):
        if subprocess.run(["git", "show-ref", "--verify", "--quiet", ref]).returncode == 0:
            return ref
    raise ValueError("no origin/HEAD, origin/main, or origin/master to read the risk policy from")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merge-base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--check-body", type=Path, help="report the expected line only when an existing line drifts")
    args = parser.parse_args()
    try:
        existing = []
        if args.check_body is not None:
            existing = [
                line for line in args.check_body.read_text(encoding="utf-8").splitlines() if line.startswith("Risk:")
            ]
            if not existing:
                return 0
        result = subprocess.run(
            [
                sys.executable,
                str(RISK_SIGNALS),
                "--merge-base",
                args.merge_base,
                "--head",
                args.head,
                "--policy-rev",
                policy_ref(),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(result.stderr.strip() or "risk-signals.py failed")
        report = json.loads(result.stdout)
        ids = ", ".join(signal["id"] for signal in report["signals"])
        details = f"signals: {ids}" if ids else "no signals"
        expected = f"Risk: {report['floor']} ({details})"
        if existing != [expected]:
            print(expected)
    except (OSError, ValueError) as error:
        print(f"Risk assessment unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
