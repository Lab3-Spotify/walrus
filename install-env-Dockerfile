FROM python:3.10.13-slim

WORKDIR /usr/src/app

RUN pip install poetry==1.6.1

COPY pyproject.toml poetry.lock ./

RUN apt-get update && \
    apt-get install vim -y \
    unzip

COPY requirements.txt requirements.txt

RUN poetry install

COPY export-requirements.sh ./

RUN chmod +x export-requirements.sh
