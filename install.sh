#!/bin/bash
# ============================================================
# Solid State — NemoClaw Setup Script
# Run this on the Hostinger VPS HOST (not inside any container)
# ============================================================
set -e

CONTAINER_NAME="solid-state"
DATA_DIR="/data/solid-state"
PORT="18790"  # sibling to Visionaire on 18789

echo "=== Solid State Setup ==="
echo "Container: $CONTAINER_NAME"
echo "Data dir:  $DATA_DIR"
echo "Port:      $PORT"
echo ""

# 1. Check Docker is available on host
if ! command -v docker &>/dev/null; then
  echo "❌ Docker not found. Install Docker first:"
  echo "   curl -fsSL https://get.docker.com | sh"
  exit 1
fi
echo "✅ Docker found: $(docker --version)"

# 2. Check Node.js >= 22.16 (NemoClaw requirement)
NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 22 ]; then
  echo "❌ Node.js 22.16+ required. Installing via nvm..."
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  source ~/.bashrc
  nvm install 22
  nvm use 22
fi
echo "✅ Node.js: $(node --version)"

# 3. Create data directory
mkdir -p "$DATA_DIR"
echo "✅ Data dir ready: $DATA_DIR"

# 4. Spin up sibling container
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "⚠️  Container $CONTAINER_NAME already exists — skipping creation"
else
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${PORT}:18789" \
    -v "${DATA_DIR}:/data/.openclaw" \
    -e "NVIDIA_API_KEY=${NVIDIA_API_KEY}" \
    -e "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" \
    node:22-bookworm-slim \
    bash -c "
      apt-get update -qq && apt-get install -y -qq curl git 2>/dev/null
      npm install -g openclaw
      openclaw start
    "
  echo "✅ Container $CONTAINER_NAME created"
fi

# 5. Install NemoClaw inside the container
echo ""
echo "=== Installing NemoClaw inside $CONTAINER_NAME ==="
docker exec -it "$CONTAINER_NAME" bash -c "curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"

echo ""
echo "=== Done ==="
echo "Connect: docker exec -it $CONTAINER_NAME nemoclaw solid-state connect"
echo "Status:  docker exec -it $CONTAINER_NAME nemoclaw solid-state status"
echo "Logs:    docker exec -it $CONTAINER_NAME nemoclaw solid-state logs --follow"
echo ""
echo "Next: copy SOUL.md, AGENTS.md, USER.md into $DATA_DIR/workspace/"
