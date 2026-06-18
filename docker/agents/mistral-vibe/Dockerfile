ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8.15
FROM ${UV_IMAGE} AS uv_source
FROM ${PYTHON_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git libasound2 libportaudio2 ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /mistral-vibe-home/home

COPY --from=uv_source /uv /uvx /usr/local/bin/

ENV VIBE_HOME=/mistral-vibe-home \
    HOME=/mistral-vibe-home/home \
    PYTHONUNBUFFERED=1 \
    NO_COLOR=1 \
    CI=1

WORKDIR /workspace

ARG MISTRAL_VIBE_VERSION=2.16.1

RUN uv pip install --system --no-cache "mistral-vibe==${MISTRAL_VIBE_VERSION}" \
    && vibe -h >/dev/null

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    '' \
    'mkdir -p "${VIBE_HOME}" "${HOME}"' \
    'if [[ -n "${HIBENCH_MISTRAL_VIBE_CONFIG:-}" ]]; then' \
    '  printf "%s\n" "${HIBENCH_MISTRAL_VIBE_CONFIG}" > "${VIBE_HOME}/config.toml"' \
    'fi' \
    '' \
    'args=("$@")' \
    'if [[ " ${args[*]} " == *" --trust "* ]] && ! vibe -h 2>&1 | grep -q -- "--trust"; then' \
    '  filtered_args=()' \
    '  for arg in "${args[@]}"; do' \
    '    [[ "${arg}" == "--trust" ]] && continue' \
    '    filtered_args+=("${arg}")' \
    '  done' \
    '  args=("${filtered_args[@]}")' \
    'fi' \
    '' \
    'exec vibe "${args[@]}"' \
    > /usr/local/bin/hibench-mistral-vibe-entrypoint \
    && chmod +x /usr/local/bin/hibench-mistral-vibe-entrypoint

ENTRYPOINT ["hibench-mistral-vibe-entrypoint"]