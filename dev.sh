#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

BACKEND_PID=""
FRONTEND_PID=""

stop_process_group() {
  local pid="$1"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  fi
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  stop_process_group "$BACKEND_PID"
  stop_process_group "$FRONTEND_PID"

  [[ -z "$BACKEND_PID" ]] || wait "$BACKEND_PID" 2>/dev/null || true
  [[ -z "$FRONTEND_PID" ]] || wait "$FRONTEND_PID" 2>/dev/null || true
  exit "$exit_code"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setsid bash -c 'cd backend && source .venv/bin/activate && exec uvicorn app.main:app --reload --port 8000' &
BACKEND_PID=$!

setsid bash -c 'cd frontend && exec npm run dev' &
FRONTEND_PID=$!

# End the development session if either service exits. The EXIT trap stops the
# remaining process group, including Uvicorn/Vite child processes.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
