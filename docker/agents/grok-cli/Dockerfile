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

RUN mkdir -p /grok-home/home/.grok /grok-home/cache /grok-home/config

ENV HOME=/grok-home/home \
    XDG_CACHE_HOME=/grok-home/cache \
    XDG_CONFIG_HOME=/grok-home/config \
    GROK_DISABLE_TELEMETRY=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG GROK_CLI_VERSION=0.2.51

RUN bun install --global "@xai-official/grok@${GROK_CLI_VERSION}" \
    && grok --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${HOME}/.grok" "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}"' \
    'if [[ -n "${HIBENCH_GROK_CONFIG:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_GROK_CONFIG}" > "${HOME}/.grok/config.toml"' \
    'fi' \
    '' \
    'exec grok "$@"' \
    > /usr/local/bin/hibench-grok-entrypoint \
    && chmod +x /usr/local/bin/hibench-grok-entrypoint

ENTRYPOINT ["hibench-grok-entrypoint"]