#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

BACKUP_ROOT=/var/backups/developer-os
STATUS_ROOT=/var/lib/developer-os-console/backup-status
LOCK_FILE=/run/lock/developer-os-postgres-backup.lock
declare -A CONTAINERS=(
  [oa]=oa_db
  [gaia]=gaia_db
  [btest]=btest-elliott-db
)
declare -A LEGACY_CONTAINERS=(
  [btest]=btest_db
)
declare -A BACKUP_POLICIES=(
  [oa]=full-cluster
  [gaia]=full-cluster
  [btest]=multi-container-excluding-market.klines-data
)
declare -A RETENTION_DAYS=(
  [oa]=14
  [gaia]=14
  [btest]=3
)

install -d -m 0700 -o root -g root "$BACKUP_ROOT"
install -d -m 0750 -o opc -g opc "$STATUS_ROOT"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "Another PostgreSQL backup is already running." >&2
  exit 1
}

update_status() {
  local project=$1
  local mode=$2
  local file=${3:-}
  local size=${4:-}
  local checksum=${5:-}
  local image=${6:-}
  local message=${7:-}
  local policy=${8:-full-cluster}
  local retention_days=${9:-14}
  local legacy_database=${10:-}
  local status_file="$STATUS_ROOT/$project.json"

  python3 - "$status_file" "$project" "$mode" "$file" "$size" "$checksum" "$image" "$message" "$policy" "$retention_days" "$legacy_database" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path, project, mode, filename, size, checksum, image, message, policy, retention_days, legacy_database = sys.argv[1:]
try:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
except (OSError, json.JSONDecodeError):
    value = {}
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
value["project"] = project
value["backup_policy"] = policy
value["retention_days"] = int(retention_days)
value["legacy_database"] = legacy_database or None
if mode == "success":
    value.update(
        {
            "last_success_at": now,
            "last_file": filename,
            "size_bytes": int(size),
            "sha256": checksum,
            "source_image": image,
            "last_error": None,
        }
    )
else:
    value["last_failure_at"] = now
    value["last_error"] = message[:500]
temporary = f"{path}.tmp"
with open(temporary, "w", encoding="utf-8") as handle:
    json.dump(value, handle, ensure_ascii=True, separators=(",", ":"))
    handle.write("\n")
os.replace(temporary, path)
PY
  chown opc:opc "$status_file"
  chmod 0600 "$status_file"
}

backup_one() {
  local project=$1
  local container=${CONTAINERS[$project]}
  local project_root="$BACKUP_ROOT/$project"
  local timestamp
  local filename
  local temporary
  local destination
  local database_user
  local image
  local checksum
  local size
  local database_name
  local legacy_container=${LEGACY_CONTAINERS[$project]:-}
  local legacy_database_name=
  local legacy_database_user=
  local policy=${BACKUP_POLICIES[$project]}
  local retention_days=${RETENTION_DAYS[$project]}
  local -a dump_command
  local dump_failed=0

  install -d -m 0700 -o root -g root "$project_root"
  if ! docker inspect "$container" >/dev/null 2>&1; then
    update_status "$project" failure "" "" "" "" "Container $container does not exist." "$policy" "$retention_days"
    return 1
  fi
  if [ "$(docker inspect "$container" --format '{{.State.Running}}')" != "true" ]; then
    update_status "$project" failure "" "" "" "" "Container $container is not running." "$policy" "$retention_days"
    return 1
  fi
  if [ -n "$legacy_container" ]; then
    if ! docker inspect "$legacy_container" >/dev/null 2>&1; then
      update_status "$project" failure "" "" "" "" "Container $legacy_container does not exist." "$policy" "$retention_days"
      return 1
    fi
    if [ "$(docker inspect "$legacy_container" --format '{{.State.Running}}')" != "true" ]; then
      update_status "$project" failure "" "" "" "" "Container $legacy_container is not running." "$policy" "$retention_days"
      return 1
    fi
    legacy_database_user=$(docker exec "$legacy_container" sh -c 'printf %s "${POSTGRES_USER:-postgres}"')
    legacy_database_name=$(docker exec "$legacy_container" sh -c 'printf %s "${POSTGRES_DB:-postgres}"')
  fi

  database_user=$(docker exec "$container" sh -c 'printf %s "${POSTGRES_USER:-postgres}"')
  database_name=$(docker exec "$container" sh -c 'printf %s "${POSTGRES_DB:-postgres}"')
  image=$(docker inspect "$container" --format '{{.Config.Image}}')
  timestamp=$(date -u +%Y%m%dT%H%M%SZ)
  filename="${project}-${timestamp}.sql.gz"
  destination="$project_root/$filename"
  temporary="${destination}.partial"

  if [ "$policy" = "multi-container-excluding-market.klines-data" ]; then
    dump_command=(
      docker exec "$container" pg_dump
      --clean --if-exists --quote-all-identifiers --no-owner --no-privileges
      --exclude-table-data=market.klines
      -U "$database_user" -d "$database_name"
    )
  else
    dump_command=(docker exec "$container" pg_dumpall --clean --if-exists --quote-all-identifiers -U "$database_user")
  fi

  if [ "$policy" = "multi-container-excluding-market.klines-data" ]; then
    (
      "${dump_command[@]}" || exit 1
      printf '\n'
      docker exec "$legacy_container" pg_dump --clean --if-exists --create --quote-all-identifiers --no-owner --no-privileges \
        -U "$legacy_database_user" -d "$legacy_database_name" || exit 1
    ) | gzip -9 >"$temporary" || dump_failed=1
  else
    "${dump_command[@]}" | gzip -9 >"$temporary" || dump_failed=1
  fi
  if [ "$dump_failed" -ne 0 ]; then
    rm -f "$temporary"
    update_status "$project" failure "" "" "" "$image" "PostgreSQL dump failed for $container." "$policy" "$retention_days" "$legacy_database_name"
    return 1
  fi
  if ! gzip -t "$temporary"; then
    rm -f "$temporary"
    update_status "$project" failure "" "" "" "$image" "Compressed backup integrity check failed." "$policy" "$retention_days" "$legacy_database_name"
    return 1
  fi

  mv "$temporary" "$destination"
  chmod 0600 "$destination"
  checksum=$(sha256sum "$destination" | awk '{print $1}')
  size=$(stat -c %s "$destination")
  printf '%s  %s\n' "$checksum" "$filename" >"${destination}.sha256"
  chmod 0600 "${destination}.sha256"
  update_status "$project" success "$filename" "$size" "$checksum" "$image" "" "$policy" "$retention_days" "$legacy_database_name"

  find "$project_root" -type f \( -name '*.sql.gz' -o -name '*.sql.gz.sha256' \) -mtime "+$((retention_days - 1))" -delete
  echo "$project backup completed: $filename"
}

projects=("$@")
if [ ${#projects[@]} -eq 0 ] || [ "${projects[0]}" = "--all" ]; then
  projects=(oa gaia btest)
fi

failed=0
for project in "${projects[@]}"; do
  if [ -z "${CONTAINERS[$project]+value}" ]; then
    echo "Unknown backup project: $project" >&2
    failed=1
    continue
  fi
  backup_one "$project" || failed=1
done
exit "$failed"
