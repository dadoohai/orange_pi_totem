#!/usr/bin/env bash
# C17.5 shell wrapper for remotely updated totem-core scripts.
# Marker: TOTEM_CORE_EXEC_WRAPPER
set -u

name="$(basename "$0")"
data_current="${TOTEM_CORE_CURRENT:-/data/core/totem/current/bin}"
fallback="${TOTEM_CORE_FALLBACK:-/opt/totem/core-fallback/bin}"

try_exec() {
  local source_label="$1"
  local target="$2"
  shift 2
  if [ -f "$target" ] && [ -r "$target" ]; then
    case "$(readlink -f "$target" 2>/dev/null || printf '%s' "$target")" in
      "$(readlink -f "$0" 2>/dev/null || printf '%s' "$0")")
        return 1
        ;;
    esac
    export TOTEM_CORE_SCRIPT_SOURCE="$source_label"
    exec /usr/bin/env bash "$target" "$@"
  fi
  return 1
}

if [ "${TOTEM_CORE_DISABLE_DATA:-}" != "1" ]; then
  try_exec data "$data_current/$name" "$@" || true
fi
try_exec fallback "$fallback/$name" "$@" || true

printf 'totem-core wrapper: no usable target for %s\n' "$name" >&2
exit 127
