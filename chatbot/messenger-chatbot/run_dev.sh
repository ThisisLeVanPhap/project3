#!/usr/bin/env bash
set -euo pipefail
export $(grep -v '^#' .env | xargs -d '\n') || true


# 1) Start API
uvicorn app.server:app --host 0.0.0.0 --port 8000 &
API_PID=$!


echo "API PID=$API_PID"


echo "Open: http://localhost:8000/healthz"
wait $API_PID