#!/usr/bin/env bash
# Adapted from EveryInc compound-engineering-plugin, ce-sessions/scripts/discover-sessions.sh.
# Upstream repository: https://github.com/EveryInc/compound-engineering-plugin
# Upstream commit reviewed: 6f9ab03a031c054a8046659926251fb6c149269f
# License: MIT, Copyright (c) 2025 Every.
# Full notice: ../references/EveryInc-LICENSE
# Local changes: Claude project folders are chosen by encoded --cwd-prefix
# instead of a repo-name glob, CLAUDE_CONFIG_DIR and CODEX_HOME relocate the
# stores, and duplicate paths are printed once.
#
# Discover session files across Claude Code, Codex, and Cursor.
#
# Usage: discover-sessions.sh <repo-name> <days> [--platform claude|codex|cursor] [--cwd-prefix PATH]...
#
# Outputs one file path per line. Safe in both bash and zsh (all globs guarded).
# Pass output to extract-metadata.py, which attributes each session by the
# working directory it recorded:
#   python3 extract-metadata.py --cwd-filter <path> $(bash discover-sessions.sh <repo-name> 7 --cwd-prefix <path>)
#
# Arguments:
#   repo-name    Folder name of the repo (e.g., "my-repo"). Used for Cursor project folders.
#   days         Scan window in days (e.g., 7). Files older than this are skipped.
#   --platform   Restrict to a single platform. Omit to search all.
#   --cwd-prefix Repository, worktree, or workspace-group path; repeatable. Claude
#                Code names each project folder after its launch directory with
#                every non-alphanumeric character replaced by "-", so only folders
#                whose names start with an encoded prefix are listed. Without a
#                prefix, every Claude project folder is listed and the metadata
#                filter does the attribution.

set -euo pipefail

REPO_NAME="${1:?Usage: discover-sessions.sh <repo-name> <days> [--platform claude|codex|cursor]}"
DAYS="${2:?Usage: discover-sessions.sh <repo-name> <days> [--platform claude|codex|cursor]}"
PLATFORM="all"
# Encoded Claude project-folder prefixes, one per line.
ENCODED_PREFIXES=""

encode_prefix() {
  printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'
}

add_prefix() {
  local prefix="${1%/}" resolved
  [ -n "$prefix" ] || return 0
  ENCODED_PREFIXES="${ENCODED_PREFIXES}$(encode_prefix "$prefix")
"
  resolved=$(CDPATH='' cd -- "$prefix" 2> /dev/null && pwd -P) || return 0
  if [ "$resolved" != "$prefix" ]; then
    ENCODED_PREFIXES="${ENCODED_PREFIXES}$(encode_prefix "$resolved")
"
  fi
}

# Parse optional flags
shift 2
while [ $# -gt 0 ]; do
  case "$1" in
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --cwd-prefix)
      add_prefix "${2:-}"
      shift 2
      ;;
    *) shift ;;
  esac
done

# --- Claude Code ---
discover_claude() {
  local base="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
  local dir name encoded matched
  [ -d "$base" ] || return 0

  for dir in "$base"/*/; do
    [ -d "$dir" ] || continue
    if [ -n "$ENCODED_PREFIXES" ]; then
      name=$(basename "$dir")
      matched=false
      while IFS= read -r encoded; do
        [ -n "$encoded" ] || continue
        case "$name" in
          "$encoded"*)
            matched=true
            break
            ;;
        esac
      done < <(printf '%s' "$ENCODED_PREFIXES")
      [ "$matched" = true ] || continue
    fi
    # Top-level transcripts only; nested subagent transcripts stay out.
    find "$dir" -maxdepth 1 -name "*.jsonl" -mtime "-${DAYS}" 2> /dev/null
  done
}

# --- Codex ---
discover_codex() {
  local base resolved seen=""
  for base in "${CODEX_HOME:-$HOME/.codex}/sessions" "$HOME/.agents/sessions"; do
    [ -d "$base" ] || continue
    # CODEX_HOME can point at the fallback store; list each directory once.
    resolved=$(CDPATH='' cd -- "$base" 2> /dev/null && pwd -P) || resolved="$base"
    if printf '%s' "$seen" | grep -Fxq -- "$resolved"; then
      continue
    fi
    seen="${seen}${resolved}
"

    # Use mtime-based discovery (consistent with Claude/Cursor) so that
    # sessions started before the scan window but still active within it
    # are not missed.
    find "$base" -name "*.jsonl" -mtime "-${DAYS}" 2> /dev/null
  done
}

# --- Cursor ---
discover_cursor() {
  local base="$HOME/.cursor/projects"
  [ -d "$base" ] || return 0

  for dir in "$base"/*"$REPO_NAME"*/; do
    [ -d "$dir" ] || continue
    local transcripts="$dir/agent-transcripts"
    [ -d "$transcripts" ] || continue
    find "$transcripts" -name "*.jsonl" -mtime "-${DAYS}" 2> /dev/null
  done
}

# --- Dispatch ---
discover() {
  case "$PLATFORM" in
    claude) discover_claude ;;
    codex) discover_codex ;;
    cursor) discover_cursor ;;
    all)
      discover_claude
      discover_codex
      discover_cursor
      ;;
    *)
      echo "Unknown platform: $PLATFORM" >&2
      return 1
      ;;
  esac
}

# Print each session path once.
discover | awk '!seen[$0]++'
