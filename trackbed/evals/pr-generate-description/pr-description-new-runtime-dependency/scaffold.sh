#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../../_lib/git-fixture.sh
. "$case_dir/../../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/retry-webhook-deliveries"
fixture_commit "$case_dir/fixtures/change" \
  "Retry failed webhook deliveries" \
  "Receivers that restart during a deploy answer 502 for a few seconds, and the event was dropped after one attempt. A delivery is now tried up to four times with backoff. Responses in the 4xx range are not retried, because the receiver rejected the event."
