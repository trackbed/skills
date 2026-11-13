#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/reject-negative-quantities"
fixture_commit "$case_dir/fixtures/change" \
  "Reject negative quantities in cart totals" \
  "A negative quantity made the total drop below zero, so a crafted cart could reduce what a customer paid. cartTotal now throws a RangeError for a negative or fractional quantity."
