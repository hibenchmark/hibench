ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8.15
FROM ${UV_IMAGE} AS uv_source
FROM ${PYTHON_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /openhands-home/home /openhands-home/cache /openhands-home/config /openhands-home/data

COPY --from=uv_source /uv /uvx /usr/local/bin/

ENV OPENHANDS_HOME=/openhands-home \
    HOME=/openhands-home/home \
    XDG_CACHE_HOME=/openhands-home/cache \
    XDG_CONFIG_HOME=/openhands-home/config \
    XDG_DATA_HOME=/openhands-home/data \
    OPENHANDS_SUPPRESS_BANNER=1 \
    OPENHANDS_DISABLE_TELEMETRY=1 \
    PYTHONUNBUFFERED=1 \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG OPENHANDS_VERSION=1.16.0

RUN uv pip install --system --no-cache "openhands==${OPENHANDS_VERSION}" \
    && openhands --version

ENTRYPOINT ["openhands"]