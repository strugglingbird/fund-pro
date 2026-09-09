#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEPLOY_URL="${DEPLOY_URL:?set DEPLOY_URL to the public site URL, for example http://203.0.113.10}"
COMPOSE=(docker compose --env-file .env.deploy)

echo "[1/5] Installing frontend dependencies"
npm ci

echo "[2/5] Building frontend"
npm run build

echo "[3/5] Replacing the complete static bundle"
mkdir -p frontend
"${COMPOSE[@]}" stop caddy
find frontend -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a dist/. frontend/

echo "[4/5] Rebuilding and starting services"
"${COMPOSE[@]}" up -d --build

echo "[5/5] Verifying deployed scripts and stylesheets"
for attempt in {1..12}; do
    if python3 scripts/verify-deployment.py "$DEPLOY_URL"; then
        "${COMPOSE[@]}" ps
        exit 0
    fi
    sleep 5
done

echo "Deployment verification failed after 12 attempts." >&2
exit 1
