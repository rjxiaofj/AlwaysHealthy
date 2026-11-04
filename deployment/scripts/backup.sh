#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${BACKUP_DIR:-$ROOT/backup_data}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$TARGET/$STAMP"

mkdir -p "$WORK"

if ! docker compose -f "$ROOT/deployment/docker-compose.yml" ps postgres --status running >/dev/null 2>&1; then
  echo "postgres 容器未运行，备份中止" >&2
  exit 1
fi

docker compose -f "$ROOT/deployment/docker-compose.yml" exec -T postgres \
  pg_dump -U alwayshealthy -d alwayshealthy -Fc > "$WORK/alwayshealthy.dump"

tar -czf "$WORK/files.tar.gz" -C "$ROOT" knowledge storage

cp -r "$ROOT/backend/app/tools/risk_engine/rules" "$WORK/rules"

tar -czf "$TARGET/alwayshealthy-$STAMP.tar.gz" -C "$TARGET" "$STAMP"
rm -rf "$WORK"

find "$TARGET" -name "alwayshealthy-*.tar.gz" -type f -mtime +7 -delete
echo "备份完成 $TARGET/alwayshealthy-$STAMP.tar.gz"
