#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

# Every test runs the template through /bin/bash, which is Bash 3.2 on macOS,
# because the template's #!/usr/bin/env bash finds that shell on a stock Mac.

setup() {
  TEMPLATE="$BATS_TEST_DIRNAME/../skills/workflow:wizard/assets/template.sh"
  LIBRARY="$BATS_TEST_TMPDIR/library.sh"
  # The wizard library is everything before the run_wizard definition.
  sed '/^run_wizard() {$/,$d' "$TEMPLATE" >"$LIBRARY"
}

@test "write_env values read back unchanged through _existing and source" {
  local value
  for value in "it's" "a'b'c" "''" '$(id) #x' ' padded ' 'back\slash "quoted"'; do
    run --separate-stderr /bin/bash -c '
      . "$1"
      ENV_FILE="$2/.env"
      write_env WIZARD_VALUE "$3" >/dev/null
      printf "%s\n" "$(_existing WIZARD_VALUE)"
      (set -a && . "$ENV_FILE" && printf "%s\n" "$WIZARD_VALUE")
    ' _ "$LIBRARY" "$BATS_TEST_TMPDIR" "$value"
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$value" ]
    [ "${lines[1]}" = "$value" ]
  done
}

@test "the final run_wizard call is parsed before the wizard runs" {
  local wizard="$BATS_TEST_TMPDIR/wizard.sh"
  {
    cat "$LIBRARY"
    cat <<'STAGES'
run_wizard() {
  printf 'ran\n' >>"$RUNS"
  # Rewrite this script in place so every byte offset below the new line moves.
  { printf '# inserted while the wizard runs\n'; cat "$0"; } >"$0.edited"
  cat "$0.edited" >"$0"
}
STAGES
    # The template's own ending, after the run_wizard definition.
    sed -n '/^run_wizard() {$/,$p' "$TEMPLATE" | sed '1,/^}$/d'
  } >"$wizard"

  RUNS="$BATS_TEST_TMPDIR/runs" run --separate-stderr /bin/bash "$wizard" </dev/null
  [ "$status" -eq 0 ]
  [ "$(wc -l <"$BATS_TEST_TMPDIR/runs")" -eq 1 ]
}
