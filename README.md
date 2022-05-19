# docker-tag-enhancer

Add major and major.minor tags to docker images that have only major.minor.patch as tags available.

## Usage

```bash
docker build -t dte . && docker run --rm -it -v /home/umars/.docker/config.json:/root/.docker/config.json dte -s gitlab/gitlab-ce -d oidatiftla/gitlab-ce -f '^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'; date
```
