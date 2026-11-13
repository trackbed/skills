#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/require-account-id"
fixture_commit "$case_dir/fixtures/change" \
  "Require accountId when listing reports" \
  "Leaving out accountId returned reports for every account the token could see. Support traced two cases of customers seeing another account's reports to clients that forgot the parameter. The parameter is now required, and a request without it gets 400. This is a major version, 3.0.0: clients must add accountId to every call to GET /v1/reports."
