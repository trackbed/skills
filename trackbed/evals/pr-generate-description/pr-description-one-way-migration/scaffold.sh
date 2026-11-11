#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/git-fixture.sh
. "$case_dir/../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/drop-legacy-plan"
fixture_commit "$case_dir/fixtures/change" \
  "Drop the legacy_plan column" \
  "Every account has had plan_id since the backfill in migration 0006, and nothing has written legacy_plan since then. The fallback in currentPlan is removed and the column is dropped. Deploy the code before running the migration, because the old code still reads the column."
