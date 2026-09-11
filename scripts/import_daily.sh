#!/bin/sh
set -eu

if [ "${FA_IMPORT_ENABLED:-false}" != "true" ]; then
  echo "FA fixture import is disabled. Set FA_IMPORT_ENABLED=true to enable it."
  exit 0
fi

while :; do
  # Keep the worker alive across transient database/provider failures. The
  # importer records per-team failures itself; this also protects the loop from
  # an unexpected process-level error.
  python -m api.import_fixtures --queued || echo "Queued fixture import failed; retrying"
  python -m api.import_fixtures || echo "Scheduled fixture import failed; retrying"
  sleep "${FA_IMPORT_INTERVAL_SECONDS:-86400}"
done
