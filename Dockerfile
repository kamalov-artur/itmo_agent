FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .[dev]

COPY src /app/src
COPY tests /app/tests
COPY README.md /app/README.md

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["sdlc-agent"]
