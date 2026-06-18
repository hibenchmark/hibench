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

RUN mkdir -p /pi-home/.pi/agent /pi-home/.pi/sessions

ENV HOME=/pi-home \
    PI_CODING_AGENT_DIR=/pi-home/.pi/agent \
    PI_CODING_AGENT_SESSION_DIR=/pi-home/.pi/sessions \
    PI_OFFLINE=1 \
    PI_SKIP_VERSION_CHECK=1 \
    PI_TELEMETRY=0 \
    npm_config_update_notifier=false \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG PI_VERSION=0.79.3

RUN pi_major="${PI_VERSION%%.*}" \
    && pi_rest="${PI_VERSION#*.}" \
    && pi_minor="${pi_rest%%.*}" \
    && if (( pi_major == 0 && pi_minor < 74 )); then \
        pi_package="@mariozechner/pi-coding-agent"; \
    else \
        pi_package="@earendil-works/pi-coding-agent"; \
    fi \
    && bun install --global --ignore-scripts "${pi_package}@${PI_VERSION}" \
    && pi --version

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${PI_CODING_AGENT_DIR}" "${PI_CODING_AGENT_SESSION_DIR}"' \
    'if [[ -n "${HIBENCH_PI_MODELS_JSON:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_PI_MODELS_JSON}" > "${PI_CODING_AGENT_DIR}/models.json"' \
    'fi' \
    '' \
    'exec pi "$@"' \
    > /usr/local/bin/hibench-pi-entrypoint \
    && chmod +x /usr/local/bin/hibench-pi-entrypoint

ENTRYPOINT ["hibench-pi-entrypoint"]