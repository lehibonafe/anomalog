#!/usr/bin/env bash
# Pull the latest Anomalog commit and redeploy the EC2 installation using the
# production DNS origin. Existing backend secrets and AWS settings are kept.
set -euo pipefail

cd "$(dirname "$0")"

PUBLIC_URL="${PUBLIC_URL:-https://anomalog.etapinc.com}"
API_BASE_URL="${API_BASE_URL:-$PUBLIC_URL}"
AWS_INCLUDE_LINKED_ACCOUNTS="${AWS_INCLUDE_LINKED_ACCOUNTS:-true}"

case "$PUBLIC_URL" in
  http://*|https://*) ;;
  *)
    echo "error: PUBLIC_URL must start with http:// or https://" >&2
    exit 1
    ;;
esac

echo "==> Pulling the latest commit (fast-forward only)..."
git pull --ff-only

echo "==> Deploying $PUBLIC_URL..."
export PUBLIC_URL API_BASE_URL AWS_INCLUDE_LINKED_ACCOUNTS
exec ./deploy.sh "$PUBLIC_URL"
