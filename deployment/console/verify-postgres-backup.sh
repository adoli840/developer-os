#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

BACKUP_ROOT=/var/backups/developer-os
STATUS_ROOT=/var/lib/developer-os-console/backup-status
LOCK_FILE=/run/lock/developer-os-postgres-verify.lock

exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "Another PostgreSQL restore verification is already running." >&2
  exit 1
}

read_status_value() {
  local path=$1
  local key=$2
  python3 - "$path" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    value = json.load(handle)
result = value.get(sys.argv[2])
print("" if result is None else result)
PY
}

write_verification() {
  local project=$1
  local result=$2
  local filename=$3
  local message=${4:-}
  local status_file="$STATUS_ROOT/$project.json"
  python3 - "$status_file" "$result" "$filename" "$message" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path, result, filename, message = sys.argv[1:]
try:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
except (OSError, json.JSONDecodeError):
    value = {}
value["verification_status"] = result
value["last_verification_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
value["verified_file"] = filename
value["verification_error"] = message[:500] if message else None
temporary = f"{path}.tmp"
with open(temporary, "w", encoding="utf-8") as handle:
    json.dump(value, handle, ensure_ascii=True, separators=(",", ":"))
    handle.write("\n")
os.replace(temporary, path)
PY
  chown opc:opc "$status_file"
  chmod 0600 "$status_file"
}

verify_one() (
  local project=$1
  local status_file="$STATUS_ROOT/$project.json"
  local filename
  local image
  local backup
  local expected_checksum
  local actual_checksum
  local verification_container="devos-restore-check-${project}-$$"
  local ready=0

  if [ ! -f "$status_file" ]; then
    echo "No backup status exists for $project." >&2
    return 1
  fi
  filename=$(read_status_value "$status_file" last_file)
  image=$(read_status_value "$status_file" source_image)
  expected_checksum=$(read_status_value "$status_file" sha256)
  backup="$BACKUP_ROOT/$project/$filename"
  if [ -z "$filename" ] || [ -z "$image" ] || [ ! -f "$backup" ]; then
    write_verification "$project" failed "$filename" "Backup file or source image metadata is missing."
    return 1
  fi
  if ! gzip -t "$backup"; then
    write_verification "$project" failed "$filename" "Compressed backup integrity check failed."
    return 1
  fi
  actual_checksum=$(sha256sum "$backup" | awk '{print $1}')
  if [ -z "$expected_checksum" ] || [ "$actual_checksum" != "$expected_checksum" ]; then
    write_verification "$project" failed "$filename" "Backup checksum validation failed."
    return 1
  fi

  cleanup() {
    docker rm -f "$verification_container" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
  docker run -d --rm --name "$verification_container" --network none \
    -e POSTGRES_USER=devos_verify \
    -e POSTGRES_DB=devos_verify \
    -e POSTGRES_HOST_AUTH_METHOD=trust "$image" >/dev/null
  for attempt in $(seq 1 60); do
    if docker exec "$verification_container" \
      psql -U devos_verify -d devos_verify -Atc "select 1;" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [ "$ready" -ne 1 ]; then
    write_verification "$project" failed "$filename" "Temporary PostgreSQL did not become ready."
    return 1
  fi
  if ! gzip -dc "$backup" | docker exec -i "$verification_container" \
    psql -v ON_ERROR_STOP=1 -U devos_verify -d devos_verify >/dev/null; then
    write_verification "$project" failed "$filename" "Isolated PostgreSQL restore failed."
    return 1
  fi
  if ! docker exec "$verification_container" psql -U devos_verify -d devos_verify -Atc \
    "select count(*) from pg_database where datistemplate = false;" | grep -Eq '^[1-9][0-9]*$'; then
    write_verification "$project" failed "$filename" "Restored database catalog validation failed."
    return 1
  fi
  write_verification "$project" passed "$filename" ""
  echo "$project isolated restore verification passed: $filename"
)

projects=("$@")
if [ ${#projects[@]} -eq 0 ] || [ "${projects[0]}" = "--all" ]; then
  projects=(oa gaia)
fi

failed=0
for project in "${projects[@]}"; do
  verify_one "$project" || failed=1
done
exit "$failed"
