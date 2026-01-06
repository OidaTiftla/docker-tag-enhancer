#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-$(basename $PROJECT_ROOT)}"
CONTAINER_NAME="${CONTAINER_NAME:-ubuntu-nix-$PROJECT_NAME-dev}"

# if container with the same name exists, reuse it
if [[ "$(docker ps -a -q -f name=${CONTAINER_NAME})" ]]; then
  docker stop "${CONTAINER_NAME}"
  docker rm "${CONTAINER_NAME}"
else
  echo "No existing container ${CONTAINER_NAME} found."
fi
