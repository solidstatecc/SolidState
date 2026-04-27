#!/bin/bash
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/SolidState}"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone https://github.com/solidstatecc/SolidState.git "$REPO_DIR"
fi
cd "$REPO_DIR"
bash agent/scripts/deploy.sh
