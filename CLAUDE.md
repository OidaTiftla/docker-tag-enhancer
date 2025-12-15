# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

docker-tag-enhancer is a Python-based tool that adds major and major.minor tags to Docker images that only have major.minor.patch tags. It reads tags from a source registry, calculates appropriate major/minor version tags, and copies them to a destination registry using skopeo.

## Core Architecture

### Main Script: src/run.py

The tool operates in three modes:

1. **Login mode** (`--login`): Authenticates to a Docker registry
2. **Tag enhancement mode** (default): Reads source tags, calculates versions, copies to destination
3. **Dual API approach**: Can use either Docker Registry REST API or skopeo CLI (via `--only-use-skopeo`)

**Key implementation details:**

- **Version parsing** (parse_version, line 193): Parses semantic versions with support for `-rc`, `-ce`, and custom suffixes. Uses regex to extract major/minor/patch components plus special suffixes.

- **Version comparison** (compare_version, line 226): Custom comparator that handles:
  - Standard semver comparisons (major.minor.patch)
  - RC (release candidate) versions as pre-releases
  - CE (community edition) tags
  - Raises exception when versions with incompatible suffixes are compared

- **Tag grouping** (lines 433-439): Groups parsed tags by major version and major.minor version to determine which tags need to be created/updated.

- **Authentication handling**:
  - Docker config file auth (get_auth_from_config, line 379)
  - Bearer token support via CLI args or token retrieval from WWW-Authenticate headers
  - Token caching to avoid redundant auth requests

- **Image copying** (mirror_image_tag, line 463): Compares digests between source and destination before copying. Uses skopeo with `--preserve-digests --all` to maintain multi-arch support.

- **Retry logic**: Rate limit handling (withRetryRateLimit, line 79) with 15-minute backoff, general retry (withRetry, line 95) with 5-minute backoff.

### Docker Registry REST API Integration

When not using `--only-use-skopeo`, the tool directly interacts with Docker Registry HTTP API v2:
- `GET /v2/<name>/tags/list` - List all tags
- `GET /v2/<name>/manifests/<tag>` - Get manifest digests for comparison
- Handles both Docker v2 manifest format and OCI image index format
- Token auth via request_docker_registry (line 352) with automatic WWW-Authenticate handling

## Development Commands

### Running locally (requires Python 3.13+, skopeo, jq)

```bash
# Install dependencies
pip install -r src/requirements.txt

# Run with arguments
python src/run.py --src <source-image> --dest <dest-image>
```

### Docker usage

```bash
# Build multi-arch image
docker buildx create --name mybuilder --use --bootstrap
docker buildx build --push --platform linux/386,linux/amd64,linux/arm/v7,linux/arm64/v8 --pull -t oidatiftla/docker-tag-enhancer .

# Run container
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer --src <source> --dest <dest>
```

### Development container

The project includes a devcontainer configuration:
- Based on Python 3.12 (Debian Bookworm)
- Includes Nix package manager and skopeo via devcontainer features
- User: ubuntu

### Nix environment

```bash
# Enter nix shell with Python 3.15
./shell.sh

# Run Claude Code via nix
./claude.sh [args]
```

## CLI Arguments

Key flags:
- `-s/--src`: Source image repository (required)
- `-d/--dest`: Destination image repository (required)
- `--prefix/--suffix`: Filter tags by prefix/suffix
- `-f/--filter`: Regex filter for tags
- `--only-new-tags`: Skip copying tags that already exist at destination
- `--update-latest`: Calculate and update the 'latest' tag
- `--no-copy`: Dry-run calculation without copying
- `--dry-run`: Print operations without executing
- `--only-use-skopeo`: Force using skopeo CLI instead of REST API

Authentication:
- `--registry-token`: Bearer token for both source and dest
- `--src-registry-token/--dest-registry-token`: Separate tokens per registry
- `--login --registry <host>`: Interactive login via skopeo

## Special Considerations

### GitHub Container Registry (GHCR)

GHCR requires base64-encoded tokens for some operations. When reading tags via skopeo:

```bash
ENCODED=$(echo -n "$GITHUB_TOKEN" | base64)
skopeo list-tags --registry-token="${ENCODED}" docker://ghcr.io/owner/image
```

### Version Parsing Edge Cases

- Versions without minor/patch components are supported (e.g., "13" is valid)
- RC and CE suffixes follow specific patterns: `-rc<num>`, `-rc<num>.ce.<num>`, `-ce.<num>`
- Arbitrary rest suffixes are preserved but treated as incomparable between different rest values
- The filter regex is applied AFTER version parsing, so only valid semver-like tags are processed

### Multi-architecture Support

The tool preserves all platform manifests when copying. Digest comparison works at the manifest list level, ensuring multi-arch images remain intact.
