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

RUN mkdir -p /kilo-home/home /kilo-home/config /kilo-home/data /kilo-home/cache /kilo-home/config-root /kilo-home/state

ENV KILO_TEST_HOME=/kilo-home/home \
    KILO_CONFIG_DIR=/kilo-home/config \
    XDG_DATA_HOME=/kilo-home/data \
    XDG_CACHE_HOME=/kilo-home/cache \
    XDG_CONFIG_HOME=/kilo-home/config-root \
    XDG_STATE_HOME=/kilo-home/state \
    KILO_DISABLE_AUTOUPDATE=1 \
    KILO_DISABLE_MODELS_FETCH=1 \
    KILO_PURE=1 \
    KILO_DB=:memory: \
    KILO_NO_DAEMON=1 \
    KILO_DISABLE_LSP_DOWNLOAD=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG KILO_VERSION=7.3.45

RUN bun install --global --ignore-scripts "@kilocode/cli@${KILO_VERSION}" \
    && kilo --version

ENTRYPOINT ["kilo"]