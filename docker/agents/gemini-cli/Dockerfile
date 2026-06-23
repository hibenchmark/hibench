ARG NODE_IMAGE=node:24-bookworm-slim
FROM ${NODE_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git ripgrep unzip \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV BUN_INSTALL=/root/.bun
ENV PATH="${BUN_INSTALL}/bin:${PATH}"

RUN curl -fsSL https://bun.com/install | bash \
    && bun --version

RUN mkdir -p /gemini-home/home/.gemini /gemini-home/cache /gemini-home/config /gemini-home/data

ENV HOME=/gemini-home/home \
    XDG_CACHE_HOME=/gemini-home/cache \
    XDG_CONFIG_HOME=/gemini-home/config \
    XDG_DATA_HOME=/gemini-home/data \
    GEMINI_API_KEY=hibench-dummy-key \
    GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key \
    GEMINI_SANDBOX=false \
    GEMINI_CLI_TRUST_WORKSPACE=true \
    NO_BROWSER=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1 \
    TERM=xterm-256color

WORKDIR /workspace

ARG GEMINI_CLI_VERSION=0.47.0

RUN bun install --global "@google/gemini-cli@${GEMINI_CLI_VERSION}" \
    && gemini --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${HOME}/.gemini" "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}"' \
    'if [[ -n "${HIBENCH_GEMINI_SETTINGS:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_GEMINI_SETTINGS}" > "${HOME}/.gemini/settings.json"' \
    'fi' \
    '' \
    'exec gemini "$@"' \
    > /usr/local/bin/hibench-gemini-entrypoint \
    && chmod +x /usr/local/bin/hibench-gemini-entrypoint

ENTRYPOINT ["hibench-gemini-entrypoint"]