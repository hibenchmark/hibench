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

RUN mkdir -p /opencode-home /opencode-config /opencode-data /opencode-cache /opencode-config-root /opencode-state

ENV OPENCODE_TEST_HOME=/opencode-home \
    OPENCODE_CONFIG_DIR=/opencode-config \
    XDG_DATA_HOME=/opencode-data \
    XDG_CACHE_HOME=/opencode-cache \
    XDG_CONFIG_HOME=/opencode-config-root \
    XDG_STATE_HOME=/opencode-state \
    OPENCODE_DISABLE_AUTOUPDATE=1 \
    OPENCODE_DISABLE_MODELS_FETCH=1 \
    OPENCODE_DISABLE_SHARE=1 \
    OPENCODE_PURE=1 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG OPENCODE_VERSION=1.17.5

RUN bun install --global "opencode-ai@${OPENCODE_VERSION}" \
    && opencode --version

# opencode fetches its runtime plugin package (@opencode-ai/plugin@<version>)
# from npm into OPENCODE_CONFIG_DIR on first run. A transient failure of that
# live fetch makes opencode exit non-zero before it contacts the recorder,
# producing a capture with zero requests. Pre-install the pinned plugin at build
# time (mirroring opencode's own generated package.json) so capture runs are
# hermetic and do not depend on a live npm fetch.
RUN printf '{"dependencies":{"@opencode-ai/plugin":"%s"}}\n' "${OPENCODE_VERSION}" \
      > /opencode-config/package.json \
    && (cd /opencode-config && npm install --no-audit --no-fund --loglevel=error) \
    && test -d /opencode-config/node_modules/@opencode-ai/plugin

ENTRYPOINT ["opencode"]