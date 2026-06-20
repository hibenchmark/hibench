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

RUN mkdir -p /droid-home/home/.factory /droid-home/cache /droid-home/config /droid-home/data

ENV HOME=/droid-home/home \
    XDG_CACHE_HOME=/droid-home/cache \
    XDG_CONFIG_HOME=/droid-home/config \
    XDG_DATA_HOME=/droid-home/data \
    FACTORY_API_KEY=fk-hibench-dummy \
    FACTORY_DROID_AUTO_UPDATE_ENABLED=false \
    FACTORYD_DISABLE_AUTO_UPDATE=1 \
    FACTORY_DISABLE_KEYRING=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG DROID_VERSION=0.153.1

RUN bun install --global "droid@${DROID_VERSION}" \
    && droid --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${HOME}/.factory" "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}"' \
    'if [[ -n "${HIBENCH_DROID_SETTINGS:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_DROID_SETTINGS}" > "${HOME}/.factory/settings.json"' \
    'fi' \
    '' \
    'exec droid "$@"' \
    > /usr/local/bin/hibench-droid-entrypoint \
    && chmod +x /usr/local/bin/hibench-droid-entrypoint

ENTRYPOINT ["hibench-droid-entrypoint"]