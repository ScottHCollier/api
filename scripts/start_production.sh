#!/bin/sh
set -eu

: "${AUTH_SECRET:?AUTH_SECRET must be set in production}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in production}"
: "${OBJECT_STORAGE_SECRET_KEY:?OBJECT_STORAGE_SECRET_KEY must be set in production}"
: "${RESEND_API_KEY:?RESEND_API_KEY must be set in production}"
: "${EMAIL_FROM:?EMAIL_FROM must be set in production}"
: "${APP_BASE_URL:?APP_BASE_URL must be set in production}"

if [ "${AUTH_SECRET}" = "change-this-development-auth-secret" ]; then
  echo "AUTH_SECRET must not use the development default" >&2
  exit 1
fi
if [ "${POSTGRES_PASSWORD}" = "final_third_dev" ]; then
  echo "POSTGRES_PASSWORD must not use the development default" >&2
  exit 1
fi
if [ "${OBJECT_STORAGE_SECRET_KEY}" = "final-third-dev-secret" ]; then
  echo "OBJECT_STORAGE_SECRET_KEY must not use the development default" >&2
  exit 1
fi
if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
  echo "SEED_ON_STARTUP must be false in production" >&2
  exit 1
fi

alembic upgrade head
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" --proxy-headers
