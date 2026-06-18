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

RUN mkdir -p /codex-home

ENV CODEX_HOME=/codex-home \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG CODEX_VERSION=0.139.0

RUN bun install --global "@openai/codex@${CODEX_VERSION}" \
    && codex --version

ENTRYPOINT ["codex"]
