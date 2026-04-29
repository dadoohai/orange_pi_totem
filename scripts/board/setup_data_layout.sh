#!/usr/bin/env bash
set -u

DATA_ROOT="/data"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

echo "Before:"
if [ -d "$DATA_ROOT" ]; then
  find "$DATA_ROOT" -maxdepth 2 -type d -printf '%M %u %g %p\n' | sort
else
  echo "$DATA_ROOT does not exist"
fi

install -d -m 0755 "$DATA_ROOT"
install -d -m 0755 "$DATA_ROOT/config"
install -d -m 0755 "$DATA_ROOT/media"
install -d -m 0755 "$DATA_ROOT/spool"
install -d -m 0755 "$DATA_ROOT/logs"

echo
echo "After:"
find "$DATA_ROOT" -maxdepth 2 -type d -printf '%M %u %g %p\n' | sort
