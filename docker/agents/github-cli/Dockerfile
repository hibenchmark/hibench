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

RUN mkdir -p /copilot-home/config /copilot-home/home /copilot-home/cache

ENV COPILOT_HOME=/copilot-home/config \
    HOME=/copilot-home/home \
    XDG_CACHE_HOME=/copilot-home/cache \
    COPILOT_OFFLINE=true \
    COPILOT_PROVIDER_TYPE=openai \
    COPILOT_PROVIDER_WIRE_API=responses \
    COPILOT_MODEL=gpt-5 \
    COPILOT_AUTO_UPDATE=false \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG GITHUB_CLI_VERSION=1.0.62

RUN bun install --global "@github/copilot@${GITHUB_CLI_VERSION}" \
    && copilot --version

ENTRYPOINT ["copilot"]