#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f backend/.env || ! -f frontend/.env ]]; then
  echo "Missing local environment files. Create them first:" >&2
  echo "  cp backend/.env.example backend/.env" >&2
  echo "  cp frontend/.env.example frontend/.env" >&2
  exit 1
fi

if [[ ! -x backend/.venv/bin/python ]]; then
  echo "Missing backend virtual environment. Follow the setup steps in README.md first." >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Missing frontend dependencies. Run 'cd frontend && npm install' first." >&2
  exit 1
fi

AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""
AWS_SESSION_TOKEN=""
AWS_REGION=""

while [[ -z "$AWS_ACCESS_KEY_ID" ]]; do
  read -r -p "AWS access key ID: " AWS_ACCESS_KEY_ID
done

while [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; do
  read -r -s -p "AWS secret access key: " AWS_SECRET_ACCESS_KEY
  echo
done

read -r -s -p "AWS session token (optional; press Enter to skip): " AWS_SESSION_TOKEN
echo

read -r -p "AWS region [ap-southeast-1]: " AWS_REGION
AWS_REGION="${AWS_REGION:-ap-southeast-1}"

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_REGION

if [[ -n "$AWS_SESSION_TOKEN" ]]; then
  export AWS_SESSION_TOKEN
else
  unset AWS_SESSION_TOKEN
fi

# A named profile takes precedence over explicitly supplied credentials here.
unset AWS_PROFILE

echo "Starting Anomalog in AWS region $AWS_REGION..."
exec ./dev.sh
