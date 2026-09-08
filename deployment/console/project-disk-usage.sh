#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: developer-os-project-disk-usage PATH" >&2
  exit 64
fi

requested=$1
resolved=$(readlink -f -- "$requested")

case "$resolved" in
  /opt/developer-os-console|/opt/developer-os-console/*|\
  /home/opc/bTest-release|/home/opc/bTest-release/*|\
  /home/opc/oa|/home/opc/oa/*|\
  /home/opc/gaia|/home/opc/gaia/*|\
  /opt/ever|/opt/ever/*)
    ;;
  *)
    echo "path is outside the managed project allowlist" >&2
    exit 65
    ;;
esac

if [[ ! -d "$resolved" ]]; then
  echo "managed project path is not a directory" >&2
  exit 66
fi

exec /usr/bin/du -sb -- "$resolved"
