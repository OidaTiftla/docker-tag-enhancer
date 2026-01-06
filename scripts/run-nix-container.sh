#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-$(basename $PROJECT_ROOT)}"
IMAGE_NAME="${IMAGE_NAME:-ubuntu-nix-$PROJECT_NAME}"
CONTAINER_NAME="${CONTAINER_NAME:-ubuntu-nix-$PROJECT_NAME-dev}"
DOCKERFILE_REL="${DOCKERFILE_REL:-docker/ubuntu-nix.Dockerfile}" # allow overrides if needed
DOCKERFILE_PATH="${PROJECT_ROOT}/${DOCKERFILE_REL}"

# if container with the same name exists, reuse it
if [[ "$(docker ps -a -q -f name=${CONTAINER_NAME})" ]]; then
  echo "Reusing existing container ${CONTAINER_NAME}..."
else
  if [[ ! -f "${DOCKERFILE_PATH}" ]]; then
    echo "Dockerfile not found at ${DOCKERFILE_PATH}" >&2
    exit 1
  fi

  echo "Building ${IMAGE_NAME} from ${DOCKERFILE_REL}..."
  docker build -f "${DOCKERFILE_PATH}" -t "${IMAGE_NAME}" "${PROJECT_ROOT}"

  # ensure nix is installed on the host
  if ! command -v nix &> /dev/null; then
    echo "Nix is not installed on the host. Please install Nix before running this script." >&2
    exit 1
  fi

  echo "Creating new container ${CONTAINER_NAME}..."
  mkdir -p "${HOME}/.codex"
  mkdir -p "${HOME}/.claude"
  mkdir -p "${HOME}/.config/ccstatusline"
  touch "${HOME}/.claude.json"
  touch "${HOME}/.claude.json.backup"
  docker run -it \
    --name "${CONTAINER_NAME}" \
    -v /nix:/nix \
    -v "${PROJECT_ROOT}:/workspace" \
    -v "${HOME}/.codex:/home/ubuntu/.codex" \
    -v "${HOME}/.claude:/home/ubuntu/.claude" \
    -v "${HOME}/.config/ccstatusline:/home/ubuntu/.config/ccstatusline" \
    -v "${HOME}/.claude.json:/home/ubuntu/.claude.json" \
    -v "${HOME}/.claude.json.backup:/home/ubuntu/.claude.json.backup" \
    -w /workspace \
    -d \
    "${IMAGE_NAME}" \
    "/bin/bash"
fi

echo "Connecting to container ${CONTAINER_NAME} (terminal-only)..."

# ensure container is running
if [[ ! "$(docker ps -q -f name=${CONTAINER_NAME})" ]]; then
  docker start "${CONTAINER_NAME}"
fi
docker exec -it "${CONTAINER_NAME}" "${@:-/bin/bash}"
