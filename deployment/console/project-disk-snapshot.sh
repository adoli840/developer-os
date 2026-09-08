#!/usr/bin/env bash
set -euo pipefail

output=/var/lib/developer-os-console/project-disk-sizes.tsv
temporary="${output}.tmp"

install -d -m 0750 -o opc -g opc /var/lib/developer-os-console
: >"$temporary"

for path in \
  /opt/developer-os-console/current \
  /home/opc/bTest-release \
  /home/opc/oa \
  /home/opc/gaia \
  /opt/ever
do
  if [[ -e "$path" ]]; then
    resolved="$(readlink -f -- "$path")"
    size="$(/usr/bin/du -sb -- "$resolved" | awk '{print $1}')"
    printf '%s\t%s\n' "$resolved" "$size" >>"$temporary"
    if [[ "$resolved" != "$path" ]]; then
      printf '%s\t%s\n' "$path" "$size" >>"$temporary"
    fi
  fi
done

chown opc:opc "$temporary"
chmod 0640 "$temporary"
mv -f -- "$temporary" "$output"
