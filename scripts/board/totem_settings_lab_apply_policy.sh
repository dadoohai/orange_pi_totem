#!/usr/bin/env bash
set -euo pipefail

MODE="status"
PRIVATE_VALUES="/tmp/dadooh-c13-1-1-private/private-values.json"
HOMOLOGATION_SEED="/data/state/totem-settings/private-values.seed.json"
REQUEST_DIR="/run/dadooh-settings"
POLICY_PATH="/run/dadooh-settings/apply-policy.json"
CONFIRM_SAVE="false"

usage() {
  cat <<'USAGE'
Usage:
  totem_settings_lab_apply_policy.sh [--status|--enable-real-write|--enable-from-homologation-seed-if-present|--clear] [options]

Options:
  --private-values /tmp/.../private-values.json
  --seed-path /data/state/totem-settings/private-values.seed.json
  --request-dir /run/dadooh-settings
  --policy-path /run/dadooh-settings/apply-policy.json
  --confirm-local-operator-save

Creates a temporary lab-only apply policy for the visual settings wizard. The
private values file is validated only by category and permissions; values are
never printed. This helper must not be used in final images.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --status)
      MODE="status"
      ;;
    --enable-real-write)
      MODE="enable-real-write"
      ;;
    --enable-from-homologation-seed-if-present)
      MODE="enable-from-homologation-seed-if-present"
      ;;
    --clear)
      MODE="clear"
      ;;
    --private-values)
      shift
      PRIVATE_VALUES="${1:-}"
      ;;
    --seed-path)
      shift
      HOMOLOGATION_SEED="${1:-}"
      ;;
    --request-dir)
      shift
      REQUEST_DIR="${1:-}"
      ;;
    --policy-path)
      shift
      POLICY_PATH="${1:-}"
      ;;
    --confirm-local-operator-save)
      CONFIRM_SAVE="true"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$MODE" in
  status|enable-real-write|enable-from-homologation-seed-if-present|clear) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac
case "$REQUEST_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --request-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$POLICY_PATH" in
  /run/*|/tmp/*) ;;
  *) echo "error: --policy-path must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$PRIVATE_VALUES" in
  /tmp/*) ;;
  *) echo "error: --private-values must be under /tmp" >&2; exit 2 ;;
esac
case "$HOMOLOGATION_SEED" in
  /data/state/totem-settings/private-values.seed.json) ;;
  *) echo "error: --seed-path must be /data/state/totem-settings/private-values.seed.json" >&2; exit 2 ;;
esac

validate_private_values() {
  local path="$1"
  local context="$2"
  python3 - "$path" "$context" <<'PY'
import json
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
context = sys.argv[2]
if path.is_symlink():
    raise SystemExit("private_values_symlink")
if context == "tmp-file":
    if not str(path).startswith("/tmp/"):
        raise SystemExit("private_values_not_tmp")
elif context == "homologation-seed":
    if str(path) != "/data/state/totem-settings/private-values.seed.json":
        raise SystemExit("homologation_seed_path_invalid")
else:
    raise SystemExit("private_values_context_invalid")
if not path.exists() or not path.is_file():
    raise SystemExit("private_values_missing")
if path.parent.is_symlink():
    raise SystemExit("private_values_parent_symlink")
parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
file_mode = stat.S_IMODE(path.stat().st_mode)
if parent_mode & 0o077:
    raise SystemExit("private_values_parent_permissive")
if file_mode & 0o077:
    raise SystemExit("private_values_file_permissive")
if not (file_mode & 0o600):
    raise SystemExit("private_values_file_not_readable_by_owner")
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit("private_values_invalid_json") from exc
if not isinstance(data, dict):
    raise SystemExit("private_values_not_object")
required = ("api_key", "api_url")
for field in required:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("private_values_required_category_missing")
for field in ("station_id", "environment_id"):
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        raise SystemExit("private_values_optional_category_invalid")
print("private_values_valid=true")
print(f"private_values_context={context}")
print(f"private_values_required_categories_present={','.join(required)}")
print("private_values_values_published=false")
PY
}

write_policy() {
  local private_path="$1"
  local private_source="$2"
  local homologation_seed="$3"
  if [ "$CONFIRM_SAVE" != "true" ]; then
    echo "error: --enable-real-write requires --confirm-local-operator-save" >&2
    exit 2
  fi
  validate_private_values "$private_path" "$private_source" >/dev/null
  install -d -m 0700 "$REQUEST_DIR"
  python3 - "$POLICY_PATH" "$private_path" "$private_source" "$homologation_seed" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
private_values = sys.argv[2]
private_source = sys.argv[3]
homologation_seed = sys.argv[4] == "true"
if not (str(target).startswith("/run/") or str(target).startswith("/tmp/")):
    raise SystemExit("policy_path_invalid")
if target.is_symlink():
    raise SystemExit("policy_symlink")
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
payload = {
    "schema_version": "dadooh-settings-apply-policy.v1",
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "mode": "real-write",
    "private_source": private_source,
    "private_values_path": private_values,
    "real_write_confirmed": True,
    "dry_run_confirmed": False,
    "active_config_private_source_confirmed": False,
    "homologation_seed": homologation_seed,
    "homologation_private_values_embedded": homologation_seed,
    "artifact_private": homologation_seed,
    "not_for_production": homologation_seed,
    "not_for_distribution": homologation_seed,
    "lab_only": True,
    "final_image": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
  printf 'policy_written=true\n'
  printf 'policy_path=%s\n' "$POLICY_PATH"
  printf 'private_values_values_published=false\n'
}

enable_from_homologation_seed_if_present() {
  if [ ! -f "$HOMOLOGATION_SEED" ]; then
    rm -f "$POLICY_PATH"
    printf 'homologation_seed_present=false\n'
    printf 'policy_written=false\n'
    printf 'policy_path=%s\n' "$POLICY_PATH"
    printf 'private_values_values_published=false\n'
    return 0
  fi
  validate_private_values "$HOMOLOGATION_SEED" "homologation-seed" >/dev/null
  CONFIRM_SAVE="true"
  write_policy "$HOMOLOGATION_SEED" "homologation-seed" "true"
  printf 'homologation_seed_present=true\n'
}

clear_policy() {
  case "$POLICY_PATH" in
    /run/*|/tmp/*)
      rm -f "$POLICY_PATH"
      ;;
  esac
  printf 'policy_present=false\n'
}

case "$MODE" in
  status)
    if [ -f "$POLICY_PATH" ]; then
      printf 'policy_present=true\n'
    else
      printf 'policy_present=false\n'
    fi
    if [ -f "$HOMOLOGATION_SEED" ]; then
      printf 'homologation_seed_present=true\n'
      validate_private_values "$HOMOLOGATION_SEED" "homologation-seed" || true
    else
      printf 'homologation_seed_present=false\n'
      validate_private_values "$PRIVATE_VALUES" "tmp-file" || true
    fi
    ;;
  enable-real-write)
    write_policy "$PRIVATE_VALUES" "tmp-file" "false"
    ;;
  enable-from-homologation-seed-if-present)
    enable_from_homologation_seed_if_present
    ;;
  clear)
    clear_policy
    ;;
esac
