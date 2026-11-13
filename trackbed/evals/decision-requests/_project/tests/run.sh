#!/usr/bin/env bash
# Runs every check for bin/duration. Exits non-zero when one fails.
set -euo pipefail

cd "$(dirname "$0")/.."
failures=0

assert_eq() {
  local actual="$1" expected="$2"
  if [ "$actual" = "$expected" ]; then
    echo "ok   $expected"
  else
    echo "FAIL expected '$expected', got '$actual'"
    failures=$((failures + 1))
  fi
}

assert_eq "$(bin/duration 3725)" "1h 2m 5s"
assert_eq "$(bin/duration 60)" "1m"
assert_eq "$(bin/duration 45)" "45s"
assert_eq "$(bin/duration 7200)" "2h"

if bin/duration abc 2> /dev/null; then
  echo "FAIL a non-number was accepted"
  failures=$((failures + 1))
else
  echo "ok   rejects a non-number"
fi

[ "$failures" -eq 0 ]
