#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

fail() {
  printf 'Deployment failed: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail 'Docker is required.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
command -v curl >/dev/null 2>&1 || fail 'curl is required for the health check.'
[[ -f backend/.env ]] || fail 'Create backend/.env from backend/.env.example first.'
api_key_line="$(sed -n 's/^ANOMALOG_API_KEY=//p' backend/.env | tail -n 1)"
api_key_line="${api_key_line%$'\r'}"
if [[ "$api_key_line" == \"*\" ]]; then
  api_key_line="${api_key_line:1:${#api_key_line}-2}"
fi
[[ ${#api_key_line} -ge 32 ]] || fail 'Set ANOMALOG_API_KEY in backend/.env to a random secret of at least 32 characters.'

http_port="${PROD_HTTP_PORT:-8080}"
[[ "$http_port" =~ ^[1-9][0-9]{0,4}$ ]] || fail 'PROD_HTTP_PORT must be a TCP port from 1 to 65535.'
(( http_port <= 65535 )) || fail 'PROD_HTTP_PORT must be a TCP port from 1 to 65535.'

export PROD_HTTP_PORT="$http_port"
compose=(docker compose --project-name anomalog-prod --file docker-compose.prod.yml)

"${compose[@]}" config --quiet
"${compose[@]}" up --detach --build --force-recreate

local_url="http://127.0.0.1:${http_port}"
ready=false
for ((attempt = 1; attempt <= 30; attempt++)); do
  if [[ "$(curl --fail --silent --max-time 3 "${local_url}/api/health" || true)" == '{"status":"ok"}' ]] && \
     curl --fail --silent --output /dev/null --max-time 3 "${local_url}/"; then
    ready=true
    break
  fi
  sleep 2
done

if [[ "$ready" != true ]]; then
  "${compose[@]}" ps >&2
  fail "The local application did not become healthy at ${local_url}."
fi

printf 'Production containers are healthy at %s\n' "$local_url"
printf 'API on this EC2 host: %s/api\n' "$local_url"
printf 'API from a container on anomalog-prod_default: http://backend:8000/api\n'
