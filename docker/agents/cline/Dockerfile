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

RUN mkdir -p /cline-home/home /cline-home/data /cline-home/xdg-data /cline-home/cache /cline-home/config /cline-home/state

ENV CLINE_DATA_DIR=/cline-home/data \
    HOME=/cline-home/home \
    XDG_DATA_HOME=/cline-home/xdg-data \
    XDG_CACHE_HOME=/cline-home/cache \
    XDG_CONFIG_HOME=/cline-home/config \
    XDG_STATE_HOME=/cline-home/state \
    CLINE_TELEMETRY_DISABLED=1 \
    CLINE_DISABLE_MIGRATION_NOTICE=1 \
    OTEL_TELEMETRY_ENABLED=false \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${CLINE_DATA_DIR}/settings" "${HOME}" "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_STATE_HOME}"' \
    'if [[ -n "${HIBENCH_CLINE_PROVIDERS_JSON:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_CLINE_PROVIDERS_JSON}" > "${CLINE_DATA_DIR}/settings/providers.json"' \
    'fi' \
    '' \
    'exec cline "$@"' \
    > /usr/local/bin/hibench-cline-entrypoint \
    && chmod +x /usr/local/bin/hibench-cline-entrypoint

WORKDIR /workspace

ARG CLINE_VERSION=3.0.24

RUN bun install --global "cline@${CLINE_VERSION}" \
    && cline --version

ENTRYPOINT ["hibench-cline-entrypoint"]