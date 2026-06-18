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

RUN mkdir -p /openclaw-home/state /openclaw-home/home

ENV OPENCLAW_STATE_DIR=/openclaw-home/state \
    OPENCLAW_CONFIG_PATH=/openclaw-home/state/openclaw.json \
    HOME=/openclaw-home/home \
    OPENCLAW_HIDE_BANNER=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG OPENCLAW_VERSION=2026.6.6

RUN bun install --global --ignore-scripts "openclaw@${OPENCLAW_VERSION}" \
    && openclaw --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${OPENCLAW_STATE_DIR}" "${HOME}"' \
    'if [[ -n "${HIBENCH_OPENCLAW_CONFIG:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_OPENCLAW_CONFIG}" > "${OPENCLAW_CONFIG_PATH}"' \
    'fi' \
    '' \
    'status=0' \
    'openclaw "$@" || status=$?' \
    'chmod -R a+rwX /workspace/.openclaw 2>/dev/null || true' \
    'exit "${status}"' \
    > /usr/local/bin/hibench-openclaw-entrypoint \
    && chmod +x /usr/local/bin/hibench-openclaw-entrypoint

ENTRYPOINT ["hibench-openclaw-entrypoint"]