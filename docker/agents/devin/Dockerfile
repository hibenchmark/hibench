FROM debian:bookworm-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        gzip \
        python3 \
        tar \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p \
        /devin-home/home \
        /devin-home/cache \
        /devin-home/config \
        /devin-home/data \
        /workspace \
    && chmod -R a+rwX /devin-home /workspace

ENV HOME=/devin-home/home \
    XDG_CACHE_HOME=/devin-home/cache \
    XDG_CONFIG_HOME=/devin-home/config \
    XDG_DATA_HOME=/devin-home/data \
    NO_COLOR=1 \
    CI=1 \
    TERM=dumb

COPY docker/agents/devin/hibench-devin-entrypoint /usr/local/bin/hibench-devin-entrypoint
RUN chmod +x /usr/local/bin/hibench-devin-entrypoint

ARG DEVIN_VERSION=2026.7.23
ARG DEVIN_PLATFORM=x86_64-unknown-linux
RUN set -eux; \
    curl -fsSL "https://static.devin.ai/cli/${DEVIN_VERSION}/manifest.json" \
        -o /tmp/devin-manifest.json; \
    DEVIN_PLATFORM="${DEVIN_PLATFORM}" python3 -c 'import json, os, shlex; manifest = json.load(open("/tmp/devin-manifest.json", encoding="utf-8")); platform = manifest["platforms"][os.environ["DEVIN_PLATFORM"]]; print("DEVIN_URL=" + shlex.quote(platform["url"])); print("DEVIN_SHA256=" + shlex.quote(platform["sha256"]))' > /tmp/devin-artifact.env; \
    source /tmp/devin-artifact.env; \
    curl -fsSL "${DEVIN_URL}" -o /tmp/devin.tar.gz; \
    echo "${DEVIN_SHA256}  /tmp/devin.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/devin; \
    tar -xzf /tmp/devin.tar.gz -C /opt/devin; \
    ln -sf /opt/devin/bin/devin /usr/local/bin/devin; \
    rm -f /tmp/devin-manifest.json /tmp/devin-artifact.env /tmp/devin.tar.gz; \
    devin --version

WORKDIR /workspace
ENTRYPOINT ["hibench-devin-entrypoint"]