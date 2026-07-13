#!/usr/bin/env sh
# Generate device-unique SSH host keys on the first production boot.

set -eu
umask 077

if [ "${1:-}" = "--self-test" ]; then
  test_root="$(mktemp -d)"
  trap 'rm -rf "$test_root"' EXIT INT TERM
  mkdir -p "$test_root/etc/ssh"
  TOTEM_PRODUCTION_IDENTITY_TEST_MODE=1 \
    TOTEM_PRODUCTION_IDENTITY_TEST_ROOT="$test_root" "$0"
  rsa_before="$(sha256sum "$test_root/etc/ssh/ssh_host_rsa_key" | awk '{print $1}')"
  ed25519_before="$(sha256sum "$test_root/etc/ssh/ssh_host_ed25519_key" | awk '{print $1}')"
  TOTEM_PRODUCTION_IDENTITY_TEST_MODE=1 \
    TOTEM_PRODUCTION_IDENTITY_TEST_ROOT="$test_root" "$0"
  test "$(sha256sum "$test_root/etc/ssh/ssh_host_rsa_key" | awk '{print $1}')" = "$rsa_before"
  test "$(sha256sum "$test_root/etc/ssh/ssh_host_ed25519_key" | awk '{print $1}')" = "$ed25519_before"
  rm -f "$test_root/etc/ssh/ssh_host_ecdsa_key.pub"
  TOTEM_PRODUCTION_IDENTITY_TEST_MODE=1 \
    TOTEM_PRODUCTION_IDENTITY_TEST_ROOT="$test_root" "$0"
  test "$(sha256sum "$test_root/etc/ssh/ssh_host_rsa_key" | awk '{print $1}')" = "$rsa_before"
  test "$(sha256sum "$test_root/etc/ssh/ssh_host_ed25519_key" | awk '{print $1}')" = "$ed25519_before"
  for key in rsa ecdsa ed25519; do
    test -s "$test_root/etc/ssh/ssh_host_${key}_key"
    test -s "$test_root/etc/ssh/ssh_host_${key}_key.pub"
  done
  echo "self-test ok"
  exit 0
fi

ROOT_PREFIX="${TOTEM_PRODUCTION_IDENTITY_TEST_ROOT:-}"
if [ -n "$ROOT_PREFIX" ] && [ "${TOTEM_PRODUCTION_IDENTITY_TEST_MODE:-0}" != "1" ]; then
  echo "BLOCKED: identity root override is test-only" >&2
  exit 2
fi
SSH_DIR="${ROOT_PREFIX}/etc/ssh"
MARKER="${ROOT_PREFIX}/var/lib/dadooh/production-identity-initialized"
MARKER_TMP="${MARKER}.tmp"

identity_complete() {
  [ -s "$MARKER" ] \
    && [ -s "$SSH_DIR/ssh_host_rsa_key" ] \
    && [ -s "$SSH_DIR/ssh_host_rsa_key.pub" ] \
    && [ -s "$SSH_DIR/ssh_host_ecdsa_key" ] \
    && [ -s "$SSH_DIR/ssh_host_ecdsa_key.pub" ] \
    && [ -s "$SSH_DIR/ssh_host_ed25519_key" ] \
    && [ -s "$SSH_DIR/ssh_host_ed25519_key.pub" ]
}

if identity_complete; then
  exit 0
fi

repair_incomplete_pair() {
  private_key="$1"
  public_key="${private_key}.pub"
  if [ ! -s "$private_key" ] || [ ! -s "$public_key" ]; then
    rm -f "$private_key" "$public_key"
  fi
}

repair_incomplete_pair "$SSH_DIR/ssh_host_rsa_key"
repair_incomplete_pair "$SSH_DIR/ssh_host_ecdsa_key"
repair_incomplete_pair "$SSH_DIR/ssh_host_ed25519_key"
if [ -n "$ROOT_PREFIX" ]; then
  ssh-keygen -A -f "$ROOT_PREFIX"
else
  ssh-keygen -A
fi

for key in \
  "$SSH_DIR/ssh_host_rsa_key" \
  "$SSH_DIR/ssh_host_ecdsa_key" \
  "$SSH_DIR/ssh_host_ed25519_key"
do
  test -s "$key"
done

install -d -m 0755 "${ROOT_PREFIX}/var/lib/dadooh"
printf '%s\n' \
  'schema=dadooh.production.identity.v1' \
  'ssh_host_keys_generated=true' \
  'storage_contract=root_ext4_rw' > "$MARKER_TMP"
chmod 0644 "$MARKER_TMP"
mv -f "$MARKER_TMP" "$MARKER"
