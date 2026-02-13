#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head 2>/dev/null || echo "No migrations to run yet"

echo "Starting Mailki Email Agent..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
