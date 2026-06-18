# Contributing

Thanks for helping improve hibench.

## Development setup

```bash
uv sync
uv run python -m hibench agents
```

The benchmark path uses Docker, so keep Docker installed and running for agent builds or
captures.

## Before opening a pull request

Run the checks that match your change:

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q hibench tests main.py
uv run ruff check .
uv run ruff format --check .
uv lock --check
```

If you change the dashboard or aggregate results:

```bash
cd web
npm ci
npm run build
```

## Adding or updating an agent

Please include:

- `agents/<agent-id>/agent.json`
- `docker/agents/<agent-id>/Dockerfile`
- parser updates and tests when generic parsing is not enough
- version catalog support when the agent has published versions
- documentation and dashboard metadata updates
- one canonical capture/export when practical

The default capture path should use dummy credentials and the local recorder so no real
upstream model call is required.
