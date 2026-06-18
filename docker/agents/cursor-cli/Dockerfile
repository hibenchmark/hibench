ARG DEBIAN_IMAGE=debian:bookworm-slim
FROM ${DEBIAN_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git tar gzip \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN mkdir -p /opt/cursor-agent-local /cursor-home/home /cursor-home/cache /cursor-home/config

ENV HOME=/cursor-home/home \
    XDG_CACHE_HOME=/cursor-home/cache \
    XDG_CONFIG_HOME=/cursor-home/config \
    CURSOR_ENABLE_AUTHLESS=1 \
    AGENT_CLI_CREDENTIAL_STORE=memory \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG CURSOR_CLI_VERSION=2026.06.12-19-59-36-f6aba9a

RUN curl -fsSL "https://downloads.cursor.com/lab/${CURSOR_CLI_VERSION}/linux/x64/agent-cli-local-package.tar.gz" \
    | tar --strip-components=1 -xzf - -C /opt/cursor-agent-local \
    && ln -s /opt/cursor-agent-local/cursor-agent-local /usr/local/bin/cursor-agent-local \
    && ln -s /opt/cursor-agent-local/cursor-agent-local /usr/local/bin/agent-local \
    && cursor-agent-local --version

ENTRYPOINT ["cursor-agent-local"]
