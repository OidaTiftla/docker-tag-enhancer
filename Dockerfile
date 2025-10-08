FROM python:3.14.0-slim

WORKDIR /usr/src/app

RUN apt update && apt install -y skopeo jq

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /root/.docker

COPY src .

ENTRYPOINT [ "python", "-u", "./run.py" ]
