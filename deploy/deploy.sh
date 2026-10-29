#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_HOST:?Set DEPLOY_HOST, e.g. ubuntu@203.0.113.10}"
: "${DEPLOY_DOMAIN:?Set DEPLOY_DOMAIN, e.g. taskflow.example.com}"
REPO_URL="${REPO_URL:-https://github.com/AnandDubey1711/taskflow.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/taskflow}"

ssh "$DEPLOY_HOST" bash -s -- "$REPO_URL" "$BRANCH" "$APP_DIR" "$DEPLOY_DOMAIN" <<'REMOTE'
set -euo pipefail
REPO_URL="$1"
BRANCH="$2"
APP_DIR="$3"
DEPLOY_DOMAIN="$4"

if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
fi

if [ ! -d "$APP_DIR/.git" ]; then
    sudo mkdir -p "$APP_DIR"
    sudo chown "$USER" "$APP_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [ ! -f .env ]; then
    umask 077
    cat > .env <<ENV
POSTGRES_PASSWORD=$(openssl rand -hex 24)
DEPLOY_DOMAIN=$DEPLOY_DOMAIN
ENV
fi

sudo docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --remove-orphans

for attempt in $(seq 1 30); do
    if curl -fsS "https://$DEPLOY_DOMAIN/health"; then
        echo
        echo "Deployed to https://$DEPLOY_DOMAIN"
        exit 0
    fi
    sleep 5
done

echo "Health check did not pass; inspect with: docker compose logs" >&2
exit 1
REMOTE
