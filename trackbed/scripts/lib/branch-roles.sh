#!/usr/bin/env bash
#
# Shared workbench selection and branch protection. Call from the target
# repository with shell-helpers.sh loaded for bounded remote lookups.

valid_branch_role_name() {
  local name="$1"
  [ -n "$name" ] && [ "$(git check-ref-format --branch "$name" 2> /dev/null)" = "$name" ]
}

read_configured_base() {
  local key status
  for key in trackbed.baseBranch kramme.baseBranch; do
    if CONFIGURED_BASE=$(git config --local --get "$key"); then
      CONFIGURED_BASE_KEY=$key
      if [ -z "$CONFIGURED_BASE" ]; then
        echo "Configured $key is empty" >&2
        return 1
      fi
      return 0
    else
      status=$?
      if [ "$status" -ne 1 ]; then
        echo "Could not read repository-local $key setting" >&2
        return 1
      fi
    fi
  done
  return 0
}

origin_default_branch() {
  local remote="$1" target status symbolic ref
  if target=$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2> /dev/null); then
    case "$target" in
      refs/remotes/origin/*)
        target=${target#refs/remotes/origin/}
        if valid_branch_role_name "$target"; then
          printf '%s\n' "$target"
          return 0
        fi
        ;;
    esac
    echo "refs/remotes/origin/HEAD does not point to a valid origin branch" >&2
    return 1
  else
    status=$?
    # Git exits 128 for a missing origin/HEAD and 1 for a non-symbolic ref.
    if [ "$status" -ne 1 ] && [ "$status" -ne 128 ]; then
      return 1
    fi
  fi

  if target=$(run_review_command 10 git ls-remote --symref -- "$remote" HEAD 2> /dev/null); then
    IFS=$'\t' read -r symbolic ref <<< "$target"
    if [ "$ref" = HEAD ] && [[ "$symbolic" == 'ref: refs/heads/'* ]]; then
      target=${symbolic#ref: refs/heads/}
      if valid_branch_role_name "$target"; then
        printf '%s\n' "$target"
      fi
    fi
  fi
}

branch_is_protected() {
  local name
  for name in "${PROTECTED_BRANCHES[@]}"; do
    [ "$name" != "$1" ] || return 0
  done
  return 1
}

# Sets CONFIGURED_BASE, CONFIGURED_BASE_KEY, CONDUCTOR_DEFAULT, REMOTE_DEFAULT,
# WORKBENCH_BASE, and PROTECTED_BRANCHES. Pass 1 to also protect develop.
# A caller with a frozen origin endpoint can pass it for the remote lookup.
# shellcheck disable=SC2034 # WORKBENCH_BASE is read by the sourcing script.
load_branch_roles() {
  local include_develop="${1:-0}" role configured_branch candidate
  CONFIGURED_BASE=""
  CONFIGURED_BASE_KEY=""
  CONDUCTOR_DEFAULT=""
  WORKBENCH_BASE=""
  PROTECTED_BRANCHES=(main master)

  read_configured_base || return
  REMOTE_DEFAULT=$(origin_default_branch "${2:-origin}") || return
  if valid_branch_role_name "${CONDUCTOR_DEFAULT_BRANCH:-}"; then
    CONDUCTOR_DEFAULT=$CONDUCTOR_DEFAULT_BRANCH
  fi

  configured_branch=$CONFIGURED_BASE
  case "$configured_branch" in
    refs/heads/*) configured_branch=${configured_branch#refs/heads/} ;;
    refs/remotes/origin/*) configured_branch=${configured_branch#refs/remotes/origin/} ;;
    origin/*) configured_branch=${configured_branch#origin/} ;;
  esac
  if [ -n "$CONFIGURED_BASE" ] && ! valid_branch_role_name "$configured_branch"; then
    echo "Configured $CONFIGURED_BASE_KEY '$CONFIGURED_BASE' is not a valid branch name" >&2
    return 1
  fi

  if [ "$include_develop" -eq 1 ]; then
    PROTECTED_BRANCHES+=(develop)
  fi
  for role in "$CONFIGURED_BASE" "$configured_branch" "$CONDUCTOR_DEFAULT" "$REMOTE_DEFAULT"; do
    if [ -n "$role" ] && ! branch_is_protected "$role"; then
      PROTECTED_BRANCHES+=("$role")
    fi
  done

  if [ -n "$configured_branch" ]; then
    WORKBENCH_BASE=$configured_branch
  elif [ -n "$CONDUCTOR_DEFAULT" ] && git show-ref --verify --quiet "refs/remotes/origin/$CONDUCTOR_DEFAULT"; then
    WORKBENCH_BASE=$CONDUCTOR_DEFAULT
  elif [ -n "$REMOTE_DEFAULT" ]; then
    WORKBENCH_BASE=$REMOTE_DEFAULT
  else
    for candidate in main master; do
      if git rev-parse --verify --quiet "refs/remotes/origin/$candidate^{commit}" > /dev/null; then
        WORKBENCH_BASE=$candidate
        break
      fi
    done
  fi
}
