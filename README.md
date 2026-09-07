# docker-tag-enhancer

[![Test, Build and Deploy](https://github.com/OidaTiftla/docker-tag-enhancer/actions/workflows/docker-deploy.yml/badge.svg)](https://github.com/OidaTiftla/docker-tag-enhancer/actions/workflows/docker-deploy.yml)

Add major and major.minor tags to docker images that have only major.minor.patch as tags available.

## Features

- 🏷️ Automatically generates major and major.minor tags from existing major.minor.patch tags
- 🐳 Multi-architecture support
- 🔍 Flexible filtering with regex, prefix, and suffix support
- ⚡ Digest-based optimization (skips copying when images are identical)
- 🧪 Comprehensive test suite
- 🚀 Automated CI/CD pipeline with GitHub Actions

## Usage

### Login

```bash
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer --login --registry registry.example.com
```

### With filter

```bash
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer -s registry.example.com/name1 -d registry.example.com/name2 -f '^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'
```

### With leading-zero version components (e.g. zero-padded timestamps)

By default, version components must not have leading zeros (`0`, `1`, `2`, ... `9`, `10`, ... but not `01`). Use `--allow-leading-zeros` if your tags contain zero-padded numbers, e.g. `0.2609.0611.1310`.

```bash
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer -s registry.example.com/name1 -d registry.example.com/name2 --allow-leading-zeros
```

### GitHub Container Registry (GHCR) read existing tags

For some reason ([source](https://github.com/orgs/community/discussions/26279#discussioncomment-3251172), [source](https://github.com/orgs/community/discussions/26279#discussioncomment-10658026)) the `GITHUB_TOKEN` needs to be encoded with `base64`:

```yaml
...

permissions:
  contents: read
  packages: write

...

jobs:
  job:
    runs-on: ubuntu-latest
    steps:

...

      - name: Retrieve tags
        run: |
          ENCODED=$(echo -n "${{ secrets.GITHUB_TOKEN }}" | base64)

          skopeo list-tags \
            --registry-token="${ENCODED}" \
            docker://${DOCKER_REGISTRY_IMAGE}
```

## Build from source

```bash
docker buildx create --name mybuilder --use --bootstrap
docker buildx build --push --platform linux/386,linux/amd64,linux/arm/v7,linux/arm64/v8 --pull -t oidatiftla/docker-tag-enhancer .
```

## Development

### Running Tests

The project includes a comprehensive test suite covering critical functionality.

```bash
# Run all tests
./test.sh
```

And the project uses `venv`. You can create a virtual environment with the following commands:

- `python -m venv venv`
- `source venv/bin/activate`
- `pip install -r src/requirements.txt`
