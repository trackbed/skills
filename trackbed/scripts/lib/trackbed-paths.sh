#!/bin/bash
# Shared resolver for trackbed state and configuration paths. Hooks load it
# through hooks/lib/check-enabled.sh and the setup checker sources it directly,
# so both resolve the same file. Precedence: an explicit override env var (or
# the KRAMME_ name it had before 1.0.0), then the XDG (or home default)
# trackbed/ directory. While that file does not exist yet, an existing file in
# the pre-1.0.0 kramme-cc-workflow/ directory and then an optional legacy path
# are used instead, so state written by earlier releases keeps working.
# Usage: resolve_trackbed_path OVERRIDE_VAR XDG_VAR XDG_DEFAULT_SUBDIR FILENAME [LEGACY_PATH]
resolve_trackbed_path() {
  local override_var="$1"
  local xdg_var="$2"
  local xdg_default_subdir="$3"
  local filename="$4"
  local legacy_path="${5:-}"
  local legacy_override_var="KRAMME_${override_var#TRACKBED_}"
  local override_value
  local xdg_base
  local default_path
  local previous_path

  override_value="${!override_var:-}"
  if [ -z "$override_value" ]; then
    override_value="${!legacy_override_var:-}"
  fi
  if [ -n "$override_value" ]; then
    printf '%s\n' "$override_value"
    return 0
  fi

  xdg_base="${!xdg_var:-}"
  if [ -z "$xdg_base" ]; then
    if [ -z "${HOME:-}" ]; then
      if [ -n "$legacy_path" ] && [ -f "$legacy_path" ]; then
        printf '%s\n' "$legacy_path"
        return 0
      fi
      return 1
    fi
    xdg_base="${HOME}/${xdg_default_subdir}"
  fi
  default_path="${xdg_base}/trackbed/${filename}"
  previous_path="${xdg_base}/kramme-cc-workflow/${filename}"

  if [ -f "$default_path" ]; then
    printf '%s\n' "$default_path"
  elif [ -f "$previous_path" ]; then
    printf '%s\n' "$previous_path"
  elif [ -n "$legacy_path" ] && [ -f "$legacy_path" ]; then
    printf '%s\n' "$legacy_path"
  else
    printf '%s\n' "$default_path"
  fi
}
