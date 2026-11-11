#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/git-fixture.sh
. "$case_dir/../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/last-seen"
fixture_commit "$case_dir/fixtures/change" "Add last_seen_at"
