#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# Keep all history recent at execution time, including after January 2027.
FIXTURE_DATE="${FIXTURE_DATE:-$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=30)).isoformat())')}"
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/../_project"
# Record the decision, then drift from it: API and CSV share a module the ADR
# rejects, and the preview keeps an older copy of the rule.
fixture_commit "$case_dir/fixtures/decision" "Record ADR-0001: keep eligibility in each channel"
fixture_commit "$case_dir/fixtures/drift" "Share next-day eligibility between API and CSV and add skerries"
# Publish the history on main, then give the fixture a feature commit.
fixture_git push --quiet origin main
fixture_branch "fixture/refactor-scan"
printf '\nLocal parcel desk workspace.\n' >> README.md
fixture_git add README.md
fixture_git commit --quiet --message "Describe the local workspace"
