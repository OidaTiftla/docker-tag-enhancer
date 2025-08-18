# docker-tag-enhancer

Add major and major.minor tags to docker images that have only major.minor.patch as tags available.

## Usage

### Login

```bash
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer --login --registry registry.example.com
```

### With filter

```bash
docker run --rm -it -v ~/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer -s registry.example.com/name1 -d registry.example.com/name2 -f '^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'
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
