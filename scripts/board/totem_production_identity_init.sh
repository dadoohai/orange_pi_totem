#!/usr/bin/env sh
# Generate device-unique SSH host keys on the first production boot.

set -eu
umask 077

MARKER="/var/lib/dadooh/production-identity-initialized"
MARKER_TMP="${MARKER}.tmp"

if [ -s "$MARKER" ]; then
  exit 0
fi

rm -f /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub
rm -f /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ecdsa_key.pub
rm -f /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub
ssh-keygen -A

for key in \
  /etc/ssh/ssh_host_rsa_key \
  /etc/ssh/ssh_host_ecdsa_key \
  /etc/ssh/ssh_host_ed25519_key
do
  test -s "$key"
done

install -d -m 0755 -o root -g root /var/lib/dadooh
printf 'schema=dadooh.production.identity.v1\nssh_host_keys_generated=true\n' > "$MARKER_TMP"
chmod 0644 "$MARKER_TMP"
mv -f "$MARKER_TMP" "$MARKER"
