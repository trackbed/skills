#!/bin/bash
# Run all BATS tests for the hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for BATS
if ! command -v bats &> /dev/null; then
  echo "ERROR: BATS is not installed."
  echo "Install with: brew install bats-core"
  echo "Or run: make install-test-deps"
  exit 1
fi

# Check for jq (required by block-rm-rf hook)
if ! command -v jq &> /dev/null; then
  echo "ERROR: jq is not installed."
  echo "Install with: brew install jq"
  echo "Or run: make install-test-deps"
  exit 1
fi

# TRACKBED_BATS_JOBS=N (N > 1) runs the full suite N files at a time. Tests
# within a file stay serial. A suite with a line starting
# `# trackbed-bats: serial` runs serially after the parallel batch; the rest of
# that line says why it is not safe to run alongside other suites.
jobs="${TRACKBED_BATS_JOBS:-1}"
case "$jobs" in
  '' | *[!0-9]*)
    echo "ERROR: TRACKBED_BATS_JOBS must be a whole number, got '$jobs'."
    exit 2
    ;;
esac
if [ "$jobs" -gt 1 ] && [ "${TRACKBED_BATS_TIMINGS:-}" = 1 ]; then
  echo "ERROR: TRACKBED_BATS_TIMINGS=1 times suites serially; unset TRACKBED_BATS_JOBS to use it."
  exit 2
fi
if [ "$jobs" -gt 1 ] && [ -z "$1" ] \
  && ! { parallel --version 2> /dev/null | grep -q '^GNU parallel'; }; then
  echo "ERROR: TRACKBED_BATS_JOBS=$jobs needs GNU parallel, which Bats uses to run suites in parallel."
  echo "Install with: brew install parallel (or apt-get install parallel)"
  echo "Or unset TRACKBED_BATS_JOBS to run the suites serially."
  exit 1
fi

# Make mock scripts executable
chmod +x test_helper/mocks/*

# Run tests
echo "Running hook tests..."
echo "============================================"

if [ "$jobs" -gt 1 ] && [ -z "$1" ]; then
  parallel_suites=()
  serial_suites=()
  for suite in *.bats; do
    if grep -q '^# trackbed-bats: serial' "$suite"; then
      serial_suites+=("$suite")
    else
      parallel_suites+=("$suite")
    fi
  done
  result=0
  bats --tap --jobs "$jobs" --no-parallelize-within-files "${parallel_suites[@]}" || result=$?
  if [ "${#serial_suites[@]}" -gt 0 ]; then
    status=0
    bats --tap "${serial_suites[@]}" || status=$?
    if [ "$result" -eq 0 ]; then
      result=$status
    fi
  fi
  if [ "$result" -ne 0 ]; then
    exit "$result"
  fi
elif [ "${TRACKBED_BATS_TIMINGS:-}" = 1 ]; then
  if [ -n "$1" ]; then
    suites=("$1")
  else
    suites=(*.bats)
  fi
  result=0
  for suite in "${suites[@]}"; do
    started=$SECONDS
    status=0
    bats --tap "$suite" || status=$?
    printf 'BATS timing: suite=%s elapsed_seconds=%s status=%s\n' \
      "$suite" "$((SECONDS - started))" "$status" >&2
    if [ "$result" -eq 0 ] && [ "$status" -ne 0 ]; then
      result=$status
    fi
  done
  if [ "$result" -ne 0 ]; then
    exit "$result"
  fi
elif [ -n "$1" ]; then
  # Run specific test file
  bats --tap "$1"
else
  # Run all tests
  bats --tap *.bats
fi

echo "============================================"
echo "All tests passed!"
