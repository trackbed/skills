#!/usr/bin/env bash
# Shared helpers for the eval suites' scaffold scripts. Each script sources
# this file and builds a small Git repository in the run's empty workspace:
# a base commit on main, a local bare "origin" holding it, and a feature
# branch with the change under test.
#
# The eval runner starts scaffold scripts with a minimal environment and a
# temporary HOME, so every Git setting the fixture needs is set here.

set -euo pipefail

FIXTURE_DATE="2026-01-15T10:00:00+00:00"

fixture_git() {
  GIT_AUTHOR_NAME="Fixture Author" \
    GIT_AUTHOR_EMAIL="fixture@example.invalid" \
    GIT_COMMITTER_NAME="Fixture Author" \
    GIT_COMMITTER_EMAIL="fixture@example.invalid" \
    GIT_AUTHOR_DATE="$FIXTURE_DATE" \
    GIT_COMMITTER_DATE="$FIXTURE_DATE" \
    git -c commit.gpgsign=false -c core.hooksPath=/dev/null "$@"
}

# Fixture manifests are stored as package.fixture.json so that dependency
# scanners do not read these invented projects as this repository's own.
fixture_copy() {
  local manifest
  cp -R "$1/." .
  find . -name package.fixture.json -not -path './.git/*' | while IFS= read -r manifest; do
    mv "$manifest" "${manifest%package.fixture.json}package.json"
  done
}

# fixture_init <base-dir>: commit the files in <base-dir> on main and publish
# them to a bare origin kept inside .git, where it stays out of `git status`.
fixture_init() {
  local base_dir="$1"
  git init --quiet --initial-branch=main .
  fixture_copy "$base_dir"
  fixture_git add --all
  fixture_git commit --quiet --message "Initial commit"
  git clone --quiet --bare . .git/fixture-origin.git
  git remote add origin "$PWD/.git/fixture-origin.git"
  git fetch --quiet origin
  git remote set-head origin main
}

# fixture_branch <name>: start the feature branch from main.
fixture_branch() {
  git checkout --quiet -b "$1"
}

# fixture_commit <overlay-dir> <subject> [body]: copy <overlay-dir> over the
# working tree and commit the result.
fixture_commit() {
  local overlay_dir="$1" subject="$2" body="${3:-}"
  fixture_copy "$overlay_dir"
  fixture_git add --all
  if [ -n "$body" ]; then
    fixture_git commit --quiet --message "$subject" --message "$body"
  else
    fixture_git commit --quiet --message "$subject"
  fi
}
