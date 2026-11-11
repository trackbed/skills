#!/usr/bin/env bash
set -euo pipefail

case_dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/git-fixture.sh
. "$case_dir/../_lib/git-fixture.sh"

fixture_init "$case_dir/fixtures/base"
fixture_branch "abildtoft/slug-accented-letters"
fixture_commit "$case_dir/fixtures/change" \
  "Keep accented letters readable in URL slugs" \
  "Titles such as Crème brûlée became cr-me-br-l-e because every letter outside a-z turned into a hyphen. Slugs now drop the accent and keep the letter. Stored slugs are not regenerated, so existing page URLs stay as they are."
