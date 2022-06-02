FROM python:bullseye

WORKDIR /usr/src/app

RUN apt update && apt install -y skopeo jq

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src .

ENTRYPOINT [ "python", "-u", "./run.py" ]
