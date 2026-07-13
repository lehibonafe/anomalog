#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

(cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
