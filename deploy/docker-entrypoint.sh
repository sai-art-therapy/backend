#!/bin/sh
set -eu

if [ "${RUN_DB_CREATE_ALL:-true}" = "true" ]; then
  python scripts/create_tables.py
fi

exec "$@"
