#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# Keep all history recent at execution time, including after January 2027.
FIXTURE_DATE="${FIXTURE_DATE:-$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=30)).isoformat())')}"
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/../_project"
# Give the tariff thirteen touches (initial + twelve) and quote only one.
for rate in 11 12 13 14 15 16 17 18 19 20 21 22; do
  python3 - "$rate" << 'PYTHON'
from pathlib import Path
import sys
p = Path("src/routing/tariff.js")
lines = p.read_text().splitlines()
lines[0] = f"export const baseRate = {sys.argv[1]};"
p.write_text("\n".join(lines) + "\n")
PYTHON
  fixture_git add src/routing/tariff.js
  fixture_git commit --quiet --message "Update parcel base rate to $rate"
done
# Publish the history on main, then give the fixture a feature commit.
fixture_git push --quiet origin main
fixture_branch "fixture/refactor-scan"
printf '\nLocal parcel desk workspace.\n' >> README.md
fixture_git add README.md
fixture_git commit --quiet --message "Describe the local workspace"
