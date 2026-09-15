#!/usr/bin/env bash
# Deploy Anomalog on a remote host (e.g. EC2) with docker compose.
#
# What it does, in order:
#   1. Detects the host's public address (EC2 IMDSv2 first, then checkip),
#      or takes it as an argument: ./deploy.sh <ip-or-dns>
#   2. Creates backend/.env and frontend/.env from their .env.example files
#      if missing, and fills in the browser-facing values that depend on the
#      public address (VITE_API_BASE_URL, CORS_ORIGINS).
#   3. Ensures GEMINI_API_KEY is set (kept from an existing .env, taken from
#      the GEMINI_API_KEY env var, or prompted for).
#   4. Builds and (re)creates both containers with docker compose.
#   5. Verifies the backend is up and can reach AWS credentials.
#
# Idempotent: safe to re-run for updates; it rewrites only the address-derived
# values and never overwrites an existing GEMINI_API_KEY.
set -euo pipefail

cd "$(dirname "$0")"

FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

# --- helpers ---------------------------------------------------------------

# set_kv <file> <key> <value> — replace the key's line, or append if absent
set_kv() {
  local file="$1" key="$2" value="$3"
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

# --- 1. resolve the public address ------------------------------------------

PUBLIC_HOST="${1:-${PUBLIC_HOST:-}}"

# On re-runs, keep the host already configured in frontend/.env (it may be a
# private/VPN address that detection below would wrongly replace)
if [ -z "$PUBLIC_HOST" ] && [ -f frontend/.env ]; then
  PUBLIC_HOST=$(grep -oP '^VITE_API_BASE_URL=https?://\K[^:/]+' frontend/.env || true)
  [ -n "$PUBLIC_HOST" ] && echo "==> Reusing configured address from frontend/.env"
fi

if [ -z "$PUBLIC_HOST" ]; then
  # EC2 instance metadata (IMDSv2); -m keeps this fast off-EC2
  token=$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
  if [ -n "$token" ]; then
    PUBLIC_HOST=$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $token" \
      http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  fi
fi

if [ -z "$PUBLIC_HOST" ]; then
  PUBLIC_HOST=$(curl -sf -m 5 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)
fi

if [ -z "$PUBLIC_HOST" ]; then
  echo "error: could not detect the public address automatically." >&2
  echo "Pass it explicitly:  ./deploy.sh <public-ip-or-dns>" >&2
  exit 1
fi

echo "==> Deploying with public address: $PUBLIC_HOST"

# --- 2 & 3. env files --------------------------------------------------------

[ -f backend/.env ]  || cp backend/.env.example backend/.env
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env

# GEMINI_API_KEY: keep existing value; else env var; else prompt
existing_key=$(grep -oP '^GEMINI_API_KEY=\K.+' backend/.env || true)
if [ -z "$existing_key" ]; then
  if [ -z "${GEMINI_API_KEY:-}" ]; then
    if [ -t 0 ]; then
      read -rsp "GEMINI_API_KEY (input hidden): " GEMINI_API_KEY
      echo
    else
      echo "error: GEMINI_API_KEY is empty in backend/.env and not provided." >&2
      echo "Re-run with:  GEMINI_API_KEY=... ./deploy.sh" >&2
      exit 1
    fi
  fi
  set_kv backend/.env GEMINI_API_KEY "$GEMINI_API_KEY"
fi

# Optional region override: AWS_REGION=... ./deploy.sh
if [ -n "${AWS_REGION:-}" ]; then
  set_kv backend/.env AWS_REGION "$AWS_REGION"
fi

# A blank AWS_PROFILE= line breaks boto3 in Docker (env_file exports it as an
# empty-string env var). The backend also guards against this in code, but
# dropping the line keeps the container env clean.
sed -i '/^AWS_PROFILE=$/d' backend/.env

# Browser-facing values — must match the origin the browser actually uses
set_kv backend/.env  CORS_ORIGINS      "[\"http://${PUBLIC_HOST}:${FRONTEND_PORT}\"]"
set_kv frontend/.env VITE_API_BASE_URL "http://${PUBLIC_HOST}:${BACKEND_PORT}"

echo "==> backend/.env and frontend/.env configured"

# --- 4. build and launch ------------------------------------------------------

# up -d (not restart) so env_file changes are picked up by recreating containers
docker compose up -d --build

# --- 5. verify -----------------------------------------------------------------

echo "==> Waiting for backend to become healthy..."
for _ in $(seq 1 30); do
  if curl -sf -o /dev/null "http://localhost:${BACKEND_PORT}/api/health"; then
    healthy=1
    break
  fi
  sleep 2
done

if [ -z "${healthy:-}" ]; then
  echo "error: backend did not become healthy. Recent logs:" >&2
  docker compose logs backend --tail 30 >&2
  exit 1
fi
echo "==> Backend is healthy"

echo "==> Checking AWS credentials inside the backend container..."
if arn=$(docker compose exec -T backend python -c \
  "import boto3; print(boto3.Session().client('sts').get_caller_identity()['Arn'])" 2>&1); then
  echo "==> AWS identity: $arn"
else
  echo "warning: the backend container could not obtain AWS credentials." >&2
  echo "$arn" >&2
  echo "On EC2 with an instance role, the usual cause is the IMDSv2 hop limit (containers need 2):" >&2
  echo "  aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2 --http-tokens required" >&2
fi

echo
echo "Deployed. Open:  http://${PUBLIC_HOST}:${FRONTEND_PORT}"
echo "Reminder: security group must allow TCP ${FRONTEND_PORT} and ${BACKEND_PORT} from your IP only — the app has no auth."
