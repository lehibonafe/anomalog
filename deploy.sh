#!/usr/bin/env bash
# Deploy Anomalog on a remote host (e.g. EC2) with docker compose.
#
# What it does, in order:
#   1. Uses PUBLIC_URL (or its first argument) as the browser-facing origin.
#      If neither is set, it reuses the current configuration or detects the
#      host's public address for a legacy direct-port HTTP deployment.
#   2. Creates backend/.env and frontend/.env from their .env.example files
#      if missing, and fills in the browser-facing values that depend on the
#      public origin (VITE_API_BASE_URL, CORS_ORIGINS).
#   3. Preserves all existing secrets and optionally applies AWS_REGION.
#   4. Builds and (re)creates both containers with docker compose.
#   5. Verifies the backend is up and can reach AWS credentials.
#
# Recommended production usage behind an HTTPS reverse proxy:
#   PUBLIC_URL=https://anomalog.example.com ./deploy.sh
#
# For a split frontend/API deployment, set API_BASE_URL separately:
#   PUBLIC_URL=https://app.example.com \
#     API_BASE_URL=https://api.example.com ./deploy.sh
#
# Idempotent: safe to re-run after updates. It rewrites only address-derived
# values and never overwrites secrets in the existing .env files.
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

# --- 1. resolve browser-facing URLs -----------------------------------------

PUBLIC_URL="${1:-${PUBLIC_URL:-}}"
API_BASE_URL="${API_BASE_URL:-}"

if [ -n "$PUBLIC_URL" ]; then
  case "$PUBLIC_URL" in
    http://*|https://*)
      PUBLIC_ORIGIN="${PUBLIC_URL%/}"
      ;;
    *)
      # Backward compatibility with the previous `./deploy.sh <ip-or-dns>`
      # interface, which exposed Vite and FastAPI directly over HTTP.
      PUBLIC_HOST="$PUBLIC_URL"
      PUBLIC_ORIGIN="http://${PUBLIC_HOST}:${FRONTEND_PORT}"
      [ -n "$API_BASE_URL" ] || API_BASE_URL="http://${PUBLIC_HOST}:${BACKEND_PORT}"
      ;;
  esac
fi

# On re-runs, keep the exact CORS origin already configured. This preserves
# HTTPS and avoids silently changing a DNS deployment back to a detected IP.
if [ -z "${PUBLIC_ORIGIN:-}" ] && [ -f backend/.env ]; then
  PUBLIC_ORIGIN=$(sed -n 's/^CORS_ORIGINS=\["\([^"]*\)"\]$/\1/p' backend/.env | head -n 1)
  [ -n "$PUBLIC_ORIGIN" ] && echo "==> Reusing configured public origin: $PUBLIC_ORIGIN"
fi

if [ -z "${PUBLIC_ORIGIN:-}" ]; then
  # EC2 instance metadata (IMDSv2); -m keeps this fast off-EC2
  token=$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
  if [ -n "$token" ]; then
    PUBLIC_HOST=$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $token" \
      http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  fi
fi

if [ -z "${PUBLIC_HOST:-}" ] && [ -z "${PUBLIC_ORIGIN:-}" ]; then
  PUBLIC_HOST=$(curl -sf -m 5 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)
fi

if [ -z "${PUBLIC_ORIGIN:-}" ] && [ -n "${PUBLIC_HOST:-}" ]; then
  PUBLIC_ORIGIN="http://${PUBLIC_HOST}:${FRONTEND_PORT}"
  [ -n "$API_BASE_URL" ] || API_BASE_URL="http://${PUBLIC_HOST}:${BACKEND_PORT}"
fi

if [ -z "${PUBLIC_ORIGIN:-}" ]; then
  echo "error: could not determine the browser-facing URL." >&2
  echo "Pass it explicitly: PUBLIC_URL=https://anomalog.example.com ./deploy.sh" >&2
  exit 1
fi

case "$PUBLIC_ORIGIN" in
  http://*|https://*) ;;
  *)
    echo "error: PUBLIC_URL must start with http:// or https://" >&2
    exit 1
    ;;
esac

# With an HTTPS reverse proxy, the API is normally served from the same origin
# under /api. Preserve an existing API URL only when no explicit public URL was
# supplied; otherwise default to the new public origin.
if [ -z "$API_BASE_URL" ]; then
  if [ -z "$PUBLIC_URL" ] && [ -f frontend/.env ]; then
    API_BASE_URL=$(sed -n 's/^VITE_API_BASE_URL=//p' frontend/.env | head -n 1)
  fi
  [ -n "$API_BASE_URL" ] || API_BASE_URL="$PUBLIC_ORIGIN"
fi
API_BASE_URL="${API_BASE_URL%/}"

echo "==> Browser origin: $PUBLIC_ORIGIN"
echo "==> Browser API URL: $API_BASE_URL"

# --- 2. env files ------------------------------------------------------------

[ -f backend/.env ]  || cp backend/.env.example backend/.env
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env

# Optional region override: AWS_REGION=... ./deploy.sh
if [ -n "${AWS_REGION:-}" ]; then
  set_kv backend/.env AWS_REGION "$AWS_REGION"
fi

# Optional monitoring-account role and CloudWatch cross-account observability
# overrides. Values already stored in backend/.env remain unchanged when the
# corresponding environment variable is absent.
if [ -n "${AWS_ROLE_ARN:-}" ]; then
  set_kv backend/.env AWS_ROLE_ARN "$AWS_ROLE_ARN"
fi
if [ -n "${AWS_ROLE_EXTERNAL_ID:-}" ]; then
  set_kv backend/.env AWS_ROLE_EXTERNAL_ID "$AWS_ROLE_EXTERNAL_ID"
fi
if [ -n "${AWS_ROLE_SESSION_NAME:-}" ]; then
  set_kv backend/.env AWS_ROLE_SESSION_NAME "$AWS_ROLE_SESSION_NAME"
fi
if [ -n "${AWS_INCLUDE_LINKED_ACCOUNTS:-}" ]; then
  set_kv backend/.env AWS_INCLUDE_LINKED_ACCOUNTS "$AWS_INCLUDE_LINKED_ACCOUNTS"
fi

# A blank AWS_PROFILE= line breaks boto3 in Docker (env_file exports it as an
# empty-string env var). The backend also guards against this in code, but
# dropping the line keeps the container env clean.
sed -i '/^AWS_PROFILE=$/d' backend/.env

# Browser-facing values — must match the origin the browser actually uses
set_kv backend/.env  CORS_ORIGINS      "[\"${PUBLIC_ORIGIN}\"]"
set_kv frontend/.env VITE_API_BASE_URL "$API_BASE_URL"

echo "==> backend/.env and frontend/.env configured"

# --- 4. build and launch ------------------------------------------------------

# Force recreation so env_file changes are always loaded after a git pull.
docker compose up -d --build --force-recreate

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

echo "==> Checking the public health endpoint..."
if curl -fsS --max-time 15 -o /dev/null "${API_BASE_URL}/api/health"; then
  echo "==> Public endpoint is healthy"
else
  echo "warning: ${API_BASE_URL}/api/health was not reachable from this host." >&2
  echo "Check the reverse proxy, DNS, TLS certificate, and ports 80/443." >&2
fi

echo "==> Checking AWS credentials inside the backend container..."
if arn=$(docker compose exec -T backend python -c \
  "from app.core.aws_session import get_boto3_session; print(get_boto3_session().client('sts').get_caller_identity()['Arn'])" 2>&1); then
  echo "==> AWS identity: $arn"
else
  echo "warning: the backend container could not obtain AWS credentials." >&2
  echo "$arn" >&2
  echo "On EC2 with an instance role, the usual cause is the IMDSv2 hop limit (containers need 2):" >&2
  echo "  aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2 --http-tokens required" >&2
fi

echo
echo "Deployed. Open: $PUBLIC_ORIGIN"
echo "Reminder: the app has no authentication; restrict access at the network or proxy layer."
