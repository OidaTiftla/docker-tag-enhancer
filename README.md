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

## Build from source

```bash
docker buildx create --name mybuilder --use --bootstrap
docker buildx build --push --platform linux/386,linux/amd64,linux/arm/v7,linux/arm64/v8 --pull -t oidatiftla/docker-tag-enhancer .
```
