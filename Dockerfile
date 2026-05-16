# ---- Stage 1: Export requirements.txt from Poetry ----
FROM python:3.10.13-slim AS builder

RUN pip install poetry==1.6.1 poetry-plugin-export

WORKDIR /build
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --without-hashes -o requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.10.13-slim

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        vim unzip procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoints/*.sh

EXPOSE 8000

ENTRYPOINT ["/usr/src/app/entrypoints/server.sh"]
