#!/bin/bash
# Solid State agent deploy — runs on Hostinger.
# Pulls latest from GitHub, rebuilds containers, restarts.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/SolidState}"
REPO_URL="${REPO_URL:-https://github.com/solidstatecc/SolidState.git}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/root/solidstate-workspace}"

echo "==> ensuring repo at $REPO_DIR"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "$REPO_URL" "$REPO_DIR"
else
  cd "$REPO_DIR" && git fetch origin && git reset --hard origin/main
fi

echo "==> ensuring workspace mount at $WORKSPACE_DIR"
mkdir -p "$WORKSPACE_DIR"
# Keep voice files synced to workspace so the brain can read them.
for f in SOUL.md AGENTS.md README.md; do
  cp "$REPO_DIR/$f" "$WORKSPACE_DIR/$f" 2>/dev/null || true
done

echo "==> checking .env"
cd "$REPO_DIR/agent"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "!! created .env from template. Fill it in, then rerun deploy.sh."
  exit 1
fi

echo "==> building + starting containers"
docker compose pull || true
docker compose up -d --build

echo "==> health check"
sleep 3
curl -fsS http://localhost:8000/health && echo "" || {
  echo "!! API failed health check. Logs:"
  docker compose logs --tail=40 api
  exit 1
}

echo "==> done. brain + api + telegram running."
docker compose ps
