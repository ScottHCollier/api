#!/bin/sh
set -eu

if [ "${FA_IMPORT_ENABLED:-false}" != "true" ]; then
  echo "FA fixture import is disabled. Set FA_IMPORT_ENABLED=true to enable it."
  exit 0
fi

full_interval="${FA_IMPORT_INTERVAL_SECONDS:-86400}"
queue_interval="${FA_IMPORT_QUEUE_INTERVAL_SECONDS:-15}"
last_full_import=0

while :; do
  # Keep queued manual syncs responsive even while scheduled imports remain
  # daily. The importer records per-team failures itself; this also protects
  # the loop from an unexpected process-level error.
  python -m api.import_fixtures --queued || echo "Queued fixture import failed; retrying"
  now=$(date +%s)
  if [ "$last_full_import" -eq 0 ] || [ $((now - last_full_import)) -ge "$full_interval" ]; then
    python -m api.import_fixtures --daily || echo "Scheduled fixture import failed; retrying"
    last_full_import=$(date +%s)
  fi
  sleep "$queue_interval"
done
