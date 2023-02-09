# docker-tag-enhancer

Add major and major.minor tags to docker images that have only major.minor.patch as tags available.

## Usage

```bash
docker run --rm -it -v /home/umars/.docker/config.json:/root/.docker/config.json oidatiftla/docker-tag-enhancer -s gitlab/gitlab-ce -d oidatiftla/gitlab-ce -f '^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'; date
```

Or run from source:

```bash
docker build --pull -t dte . && docker run --rm -it -v /home/umars/.docker/config.json:/root/.docker/config.json dte -s gitlab/gitlab-ce -d oidatiftla/gitlab-ce -f '^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'; date
```

## Build from source

```bash
docker buildx create --name mybuilder --use --bootstrap
docker buildx build --push --platform linux/386,linux/amd64,linux/arm,linux/arm64 --pull -t oidatiftla/docker-tag-enhancer .
```
