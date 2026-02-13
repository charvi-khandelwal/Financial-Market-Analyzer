#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ -f "$BACKEND_DIR/ve/bin/activate" ]]; then
  # Unix-style virtual environment
  # shellcheck disable=SC1091
  source "$BACKEND_DIR/ve/bin/activate"
elif [[ -f "$BACKEND_DIR/ve/Scripts/activate" ]]; then
  # Windows-style virtual environment used from Git Bash
  # shellcheck disable=SC1091
  source "$BACKEND_DIR/ve/Scripts/activate"
else
  echo "Virtual environment activate script not found in backend/ve."
  exit 1
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  npm run dev
)
