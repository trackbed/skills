#!/usr/bin/env bash
#
# Local wrapper around the shared dev-server detection scripts. It is inspired
# by the ce-polish detection cascade cited in this directory, but is not copied
# from upstream: this script adds the trackbed workflow URL contract.
#
# Output contract:
#   http://localhost:<port>      - one reachable URL was resolved
#   __NO_RUNNING_SERVER__        - no reachable dev server was found
#   __MULTIPLE_URLS__ + lines    - multiple reachable URLs need disambiguation
#
# With --check-owner, a URL the detector found itself (not an explicit --url or
# --port) is checked against the checkout that serves it:
#   __FOREIGN_SERVER__ + lines   - every hit is served from another checkout;
#                                  each line is "<url><TAB><checkout root>"
#   __UNCONFIRMED_OWNER__ + url  - one hit whose serving checkout is unknown

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=../lib/shell-helpers.sh
source "$SCRIPT_DIR/../lib/shell-helpers.sh"
PROJECT_ROOT=""
EXPLICIT_URL=""
EXPLICIT_PORT=""
PROJECT_TYPE=""
LAUNCH_CONFIG=""
APP_CANDIDATES=""
CHECK_OWNER=false
TAB=$'\t'

while [ $# -gt 0 ]; do
  case "$1" in
    auto)
      shift
      ;;
    --url)
      require_value "$1" "${2-}" 1 "ERROR: "
      EXPLICIT_URL="${2:-}"
      shift 2
      ;;
    --port)
      require_value "$1" "${2-}" 1 "ERROR: "
      EXPLICIT_PORT="${2:-}"
      shift 2
      ;;
    --type)
      require_value "$1" "${2-}" 1 "ERROR: "
      PROJECT_TYPE="${2:-}"
      shift 2
      ;;
    --launch-config)
      require_value "$1" "${2-}" 1 "ERROR: "
      LAUNCH_CONFIG="${2:-}"
      shift 2
      ;;
    --check-owner)
      CHECK_OWNER=true
      shift
      ;;
    *)
      if printf '%s' "$1" | grep -qE '^https?://'; then
        EXPLICIT_URL="$1"
      elif [ -z "$PROJECT_ROOT" ]; then
        PROJECT_ROOT="$1"
      fi
      shift
      ;;
  esac
done

if [ -z "$PROJECT_ROOT" ]; then
  PROJECT_ROOT=$(git rev-parse --show-toplevel 2> /dev/null || true)
  if [ -z "$PROJECT_ROOT" ]; then
    echo "ERROR: not in a git repository and no path provided" >&2
    exit 1
  fi
fi

if [ ! -d "$PROJECT_ROOT" ]; then
  echo "ERROR: path does not exist: $PROJECT_ROOT" >&2
  exit 1
fi

is_port() {
  local value="$1"
  case "$value" in
    '' | *[!0-9]*) return 1 ;;
  esac
  [ "$value" -ge 1 ] 2> /dev/null && [ "$value" -le 65535 ] 2> /dev/null
}

verify_url() {
  local url="$1"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2> /dev/null || true)
  case "$status" in
    2?? | 3?? | 4??) return 0 ;;
    *) return 1 ;;
  esac
}

try_port() {
  local port="$1"
  if ! is_port "$port"; then
    return 1
  fi
  local url="http://localhost:${port}"
  if verify_url "$url"; then
    printf '%s\n' "$url"
    return 0
  fi
  return 1
}

canonical_dir() {
  (CDPATH='' cd -- "$1" 2> /dev/null && pwd -P)
}

# Print the working directory of the process listening on a local TCP port,
# or nothing when no inspection tool can tell.
listener_cwd() {
  local port="$1" pid=""
  if command -v lsof > /dev/null 2>&1; then
    pid=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2> /dev/null | head -n 1 || true)
    if [ -n "$pid" ]; then
      lsof -a -p "$pid" -d cwd -Fn 2> /dev/null | sed -n 's/^n//p' | head -n 1 || true
      return 0
    fi
  fi
  if command -v ss > /dev/null 2>&1; then
    pid=$(ss -ltnp "sport = :$port" 2> /dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1 || true)
    if [ -n "$pid" ] && [ -e "/proc/$pid/cwd" ]; then
      readlink "/proc/$pid/cwd" 2> /dev/null || true
    fi
  fi
}

# Print "owned", "foreign:<checkout root>", or "unknown" for a resolved
# localhost URL. A server counts as foreign only when its working directory
# sits in another Git checkout, such as a sibling worktree or the main
# checkout. Container proxies and servers outside any checkout stay unknown.
server_owner() {
  local url="$1" port cwd owner_root this_root
  port="${url##*:}"
  port="${port%%/*}"
  if ! is_port "$port"; then
    echo unknown
    return 0
  fi
  cwd=$(listener_cwd "$port" || true)
  if [ -z "$cwd" ] || [ ! -d "$cwd" ]; then
    echo unknown
    return 0
  fi
  owner_root=$(git -C "$cwd" rev-parse --show-toplevel 2> /dev/null || true)
  [ -n "$owner_root" ] && owner_root=$(canonical_dir "$owner_root" || true)
  this_root=$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2> /dev/null || printf '%s' "$PROJECT_ROOT")
  this_root=$(canonical_dir "$this_root" || true)
  if [ -z "$owner_root" ] || [ -z "$this_root" ]; then
    echo unknown
    return 0
  fi
  case "$owner_root/" in
    "$this_root"/*) echo owned ;;
    *) echo "foreign:$owner_root" ;;
  esac
}

# Print one URL the detector resolved itself, applying --check-owner.
emit_resolved() {
  local url="$1" owner
  if [ "$CHECK_OWNER" != true ]; then
    printf '%s\n' "$url"
    return 0
  fi
  owner=$(server_owner "$url" || true)
  case "$owner" in
    owned)
      printf '%s\n' "$url"
      ;;
    foreign:*)
      echo "__FOREIGN_SERVER__"
      printf '%s\t%s\n' "$url" "${owner#foreign:}"
      ;;
    *)
      echo "__UNCONFIRMED_OWNER__"
      printf '%s\n' "$url"
      ;;
  esac
}

# Print the outcome for a newline-separated list of reachable URLs. With
# --check-owner, URLs served from another checkout are dropped before counting.
emit_candidates() {
  local urls kept="" foreign="" url owner line count
  urls=$(printf '%s\n' "$1" | sed '/^$/d')
  if [ "$CHECK_OWNER" = true ] && [ -n "$urls" ]; then
    while IFS= read -r url; do
      [ -n "$url" ] || continue
      owner=$(server_owner "$url" || true)
      case "$owner" in
        foreign:*) foreign="${foreign}${url}${TAB}${owner#foreign:}
" ;;
        *) kept="${kept}${url}
" ;;
      esac
    done < <(printf '%s\n' "$urls")
    if [ -z "$kept" ] && [ -n "$foreign" ]; then
      echo "__FOREIGN_SERVER__"
      printf '%s' "$foreign"
      return 0
    fi
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      printf 'NOTE: skipped %s, served from another checkout: %s\n' "${line%%"$TAB"*}" "${line#*"$TAB"}" >&2
    done < <(printf '%s' "$foreign")
    urls=$(printf '%s' "$kept" | sed '/^$/d')
  fi
  count=$(printf '%s\n' "$urls" | sed '/^$/d' | wc -l | tr -d ' ')
  case "$count" in
    0)
      echo "__NO_RUNNING_SERVER__"
      ;;
    1)
      emit_resolved "$urls"
      ;;
    *)
      echo "__MULTIPLE_URLS__"
      printf '%s\n' "$urls"
      ;;
  esac
}

if [ -n "$EXPLICIT_URL" ]; then
  if ! printf '%s' "$EXPLICIT_URL" | grep -qE '^https?://'; then
    echo "ERROR: explicit URL must start with http:// or https://: $EXPLICIT_URL" >&2
    exit 1
  fi
  if verify_url "$EXPLICIT_URL"; then
    echo "$EXPLICIT_URL"
  else
    echo "__NO_RUNNING_SERVER__"
  fi
  exit 0
fi

if [ -n "$EXPLICIT_PORT" ]; then
  if ! is_port "$EXPLICIT_PORT"; then
    echo "ERROR: explicit port must be between 1 and 65535: $EXPLICIT_PORT" >&2
    exit 1
  fi
  resolved_url=$(try_port "$EXPLICIT_PORT" || true)
  if [ -n "$resolved_url" ]; then
    echo "$resolved_url"
  else
    echo "__NO_RUNNING_SERVER__"
  fi
  exit 0
fi

APP_ROOT="$PROJECT_ROOT"

if [ -z "$PROJECT_TYPE" ]; then
  detected_type=$("$SCRIPT_DIR/detect-project-type.sh" "$PROJECT_ROOT" 2> /dev/null || true)
  case "$detected_type" in
    multiple:*)
      APP_CANDIDATES="${detected_type#multiple:}"
      PROJECT_TYPE=""
      ;;
    *@*)
      PROJECT_TYPE="${detected_type%@*}"
      rel_dir="${detected_type#*@}"
      APP_ROOT="$PROJECT_ROOT/$rel_dir"
      ;;
    multiple*)
      PROJECT_TYPE=""
      ;;
    unknown | "")
      PROJECT_TYPE=""
      ;;
    *)
      PROJECT_TYPE="$detected_type"
      ;;
  esac
fi

LAUNCH_PORT=""
if command -v jq > /dev/null 2>&1; then
  launch_json=$("$SCRIPT_DIR/read-launch-json.sh" --root "$PROJECT_ROOT" "$LAUNCH_CONFIG" 2> /dev/null || true)
  if printf '%s' "$launch_json" | grep -q '^{'; then
    LAUNCH_PORT=$(printf '%s' "$launch_json" | jq -r '.port // empty' 2> /dev/null || true)
  elif printf '%s' "$launch_json" | grep -q '^__MULTIPLE_CONFIGS__$'; then
    launch_urls=""
    while IFS= read -r launch_port; do
      [ -n "$launch_port" ] || continue
      launch_url=$(try_port "$launch_port" || true)
      if [ -n "$launch_url" ] && ! printf '%s\n' "$launch_urls" | grep -Fxq "$launch_url"; then
        launch_urls="${launch_urls}
${launch_url}"
      fi
    done < <(
      jq -r '
        .configurations[]
        | .port // empty
        | select(type == "number" or type == "string")
      ' "$PROJECT_ROOT/.claude/launch.json" 2> /dev/null || true
    )

    emit_candidates "$launch_urls"
    exit 0
  elif [ -n "$LAUNCH_CONFIG" ]; then
    case "$launch_json" in
      __NO_LAUNCH_JSON__)
        echo "ERROR: .claude/launch.json not found for launch configuration: $LAUNCH_CONFIG" >&2
        ;;
      __INVALID_LAUNCH_JSON__)
        echo "ERROR: .claude/launch.json is invalid" >&2
        ;;
      __MISSING_CONFIGURATIONS__)
        echo "ERROR: .claude/launch.json has no configurations" >&2
        ;;
      __CONFIG_NOT_FOUND__)
        echo "ERROR: launch configuration not found: $LAUNCH_CONFIG" >&2
        ;;
      *)
        echo "ERROR: unable to read launch configuration: $LAUNCH_CONFIG" >&2
        ;;
    esac
    echo "__NO_RUNNING_SERVER__"
    exit 0
  fi
fi

# A port declared by the selected or only launch configuration is final: when it
# does not answer, stop rather than return whatever else answers on a common port.
if is_port "$LAUNCH_PORT"; then
  resolved_url=$(try_port "$LAUNCH_PORT" || true)
  if [ -n "$resolved_url" ]; then
    emit_resolved "$resolved_url"
  else
    echo "NOTE: launch configuration port $LAUNCH_PORT did not answer; not trying other ports" >&2
    echo "__NO_RUNNING_SERVER__"
  fi
  exit 0
fi

if [ -n "$APP_CANDIDATES" ]; then
  candidate_urls=""
  while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    case "$candidate" in
      *@*)
        candidate_type="${candidate%@*}"
        candidate_dir="${candidate#*@}"
        candidate_root="$PROJECT_ROOT/$candidate_dir"
        ;;
      *)
        continue
        ;;
    esac

    candidate_port=$("$SCRIPT_DIR/resolve-port.sh" "$candidate_root" --type "$candidate_type" 2> /dev/null || true)
    candidate_url=$(try_port "$candidate_port" || true)
    if [ -n "$candidate_url" ] && ! printf '%s\n' "$candidate_urls" | grep -Fxq "$candidate_url"; then
      candidate_urls="${candidate_urls}
${candidate_url}"
    fi
  done < <(printf '%s\n' "$APP_CANDIDATES" | tr ',' '\n')

  emit_candidates "$candidate_urls"
  exit 0
fi

RESOLVED_PORT=$("$SCRIPT_DIR/resolve-port.sh" "$APP_ROOT" --type "$PROJECT_TYPE" 2> /dev/null || true)
if is_port "$RESOLVED_PORT"; then
  resolved_url=$(try_port "$RESOLVED_PORT" || true)
  if [ -n "$resolved_url" ]; then
    emit_resolved "$resolved_url"
    exit 0
  fi
fi

# Conductor reserves ten workspace-specific ports; prefer them over sibling common-port servers.
if is_port "${CONDUCTOR_PORT:-}"; then
  for offset in 0 1 2 3 4 5 6 7 8 9; do
    resolved_url=$(try_port "$((CONDUCTOR_PORT + offset))" || true)
    if [ -n "$resolved_url" ]; then
      emit_resolved "$resolved_url"
      exit 0
    fi
  done
fi

COMMON_PORTS="3000 3001 4200 4201 4321 5000 5173 5174 8000 8080 8888 9000"
FOUND_URLS=""

for port in $COMMON_PORTS; do
  url=$(try_port "$port" || true)
  if [ -n "$url" ] && ! printf '%s\n' "$FOUND_URLS" | grep -Fxq "$url"; then
    FOUND_URLS="${FOUND_URLS}
${url}"
  fi
done

emit_candidates "$FOUND_URLS"
