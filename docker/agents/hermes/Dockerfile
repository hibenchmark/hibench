ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG NODE_IMAGE=node:22-bookworm-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8.15
FROM ${NODE_IMAGE} AS node_source
FROM ${UV_IMAGE} AS uv_source
FROM ${PYTHON_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git ripgrep \
        fonts-freefont-ttf fonts-noto-cjk fonts-noto-color-emoji \
        libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
        libcairo-gobject2 libcairo2 libcups2 libdbus-1-3 libdrm2 libfontconfig1 \
        libfreetype6 libgbm1 libgdk-pixbuf-2.0-0 libglib2.0-0 libgtk-3-0 \
        libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libx11-6 \
        libx11-xcb1 libxcb-shm0 libxcb1 libxcomposite1 libxcursor1 \
        libxdamage1 libxext6 libxfixes3 libxi6 libxkbcommon0 libxrandr2 \
        libxrender1 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /hermes-home/home

COPY --from=node_source /usr/local/ /usr/local/
COPY --from=uv_source /uv /uvx /usr/local/bin/

ENV HERMES_HOME=/hermes-home \
    HOME=/hermes-home/home \
    PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright \
    AGENT_BROWSER_EXECUTABLE_PATH=/usr/local/bin/hermes-chrome \
    HERMES_SKIP_NODE_BOOTSTRAP=1 \
    HERMES_CONTAINER=1 \
    HERMES_SKIP_CHMOD=1 \
    PYTHONUNBUFFERED=1 \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG AGENT_BROWSER_VERSION=0.26.0

RUN npm install --global --ignore-scripts "agent-browser@${AGENT_BROWSER_VERSION}" \
    && agent-browser install \
    && chrome_path="$(find "${HOME}/.agent-browser/browsers" -type f -name chrome -perm /111 | head -n 1)" \
    && test -n "${chrome_path}" \
    && ln -sf "${chrome_path}" /usr/local/bin/hermes-chrome \
    && hermes-chrome --version \
    && npm cache clean --force \
    && agent-browser --version

ARG HERMES_VERSION=0.16.0

RUN uv pip install --system --no-cache "hermes-agent==${HERMES_VERSION}" \
    && hermes --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${HERMES_HOME}" "${HOME}"' \
    'if [[ -n "${HIBENCH_HERMES_CONFIG:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_HERMES_CONFIG}" > "${HERMES_HOME}/config.yaml"' \
    'fi' \
    '' \
    'exec hermes "$@"' \
    > /usr/local/bin/hibench-hermes-entrypoint \
    && chmod +x /usr/local/bin/hibench-hermes-entrypoint

ENTRYPOINT ["hibench-hermes-entrypoint"]
