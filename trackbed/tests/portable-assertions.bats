#!/usr/bin/env bats

# Run actual nested Bats tests so failure must survive its trap and subprocesses.
assert_fixture_status() {
  local expected="$1" assertion="$2"
  rm -f "$BATS_TEST_TMPDIR/reached-later"
  printf '@test "assertion control" {\n  %s\n  touch "%s"\n}\n' "$assertion" "$BATS_TEST_TMPDIR/reached-later" >"$BATS_TEST_TMPDIR/control.bats"
  run bats --tap "$BATS_TEST_TMPDIR/control.bats"
  [ "$status" -eq "$expected" ]
  if [ "$expected" -ne 0 ]; then
    [[ "$output" == *'not ok 1'* ]] || false
    [ ! -e "$BATS_TEST_TMPDIR/reached-later" ]
  else
    [ -e "$BATS_TEST_TMPDIR/reached-later" ]
  fi
}

@test "guarded false assertions fail before a later successful command" {
  assert_fixture_status 1 '! true || false'
  assert_fixture_status 1 $'!\ttrue || false'
  assert_fixture_status 1 $'[[\ta == b ]] || false'
  assert_fixture_status 1 $'[[\n a == b\n]] || false'
  assert_fixture_status 1 $'! true || {\n echo failure\n return 1\n}'
  assert_fixture_status 1 '[[ a == b ]] || false'
  assert_fixture_status 1 '[[ a == b ]] || [[ c == d ]] || false'
}

@test "guarded positive assertions preserve success" {
  assert_fixture_status 0 '! false || false'
  assert_fixture_status 0 $'!\tfalse || false'
  assert_fixture_status 0 $'[[\ta == a ]] || false'
  assert_fixture_status 0 $'[[\n a == a\n]] || false'
  assert_fixture_status 0 $'! false || {\n echo failure\n return 1\n}'
  assert_fixture_status 0 '[[ a == a ]] || false'
  assert_fixture_status 0 '[[ a == b ]] || [[ c == c ]] || false'
}

@test "recurrence check rejects successful OR fallbacks that hide a false assertion" {
  local assertion
  for assertion in '! true || echo failure || false' '! true || true || false' '[[ a == b ]] || echo failure || false' '[[ a == b ]] || true || false'; do
    assert_fixture_status 0 "$assertion"
    run python3 "$BATS_TEST_DIRNAME/test_helper/check_bats_assertions.py" "$BATS_TEST_TMPDIR/control.bats"
    [ "$status" -eq 1 ]
    [[ "$output" == *'assertion needs an explicit failure guard'* ]] || false
  done
}
