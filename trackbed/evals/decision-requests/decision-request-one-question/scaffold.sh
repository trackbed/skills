#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/../_project"
fixture_branch "abildtoft/round-to-minutes"
fixture_commit "$case_dir/fixtures/change" "Add the plan for rounding durations to minutes"
