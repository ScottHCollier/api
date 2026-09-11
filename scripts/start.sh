#!/bin/sh
set -eu

alembic upgrade head
python -m api.seed --if-enabled
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/src
