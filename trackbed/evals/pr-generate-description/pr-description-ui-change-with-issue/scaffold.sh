#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/git-fixture.sh
. "$case_dir/../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/skills-15-export-results-csv"
fixture_commit "$case_dir/fixtures/change" \
  "Add a CSV export button to the results page" \
  "People asked to share survey results with colleagues who have no account. The results page now has an Export CSV button that downloads the rows shown in the table."
