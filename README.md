<h1 align="center"><code>Hi</code>bench</h1>

Compare the hidden default footprint of coding agents.

hibench runs a coding agent in an isolated Docker container against an empty workspace
folder, prompts it with `Hi`, captures the first outbound model request with a local
recorder, and reports how much context, tooling, MCP surface, sub-agent surface, and
skill metadata the agent injects before user work begins.

No provider account or real upstream model call is required for the default benchmark
path: hibench uses dummy API keys and returns a synthetic successful completion.

- Dashboard: <https://hibench.dev>
- Source: <https://github.com/hibenchmark/hibench>

## What it measures

- Total primary request body tokens
- System/developer/default context tokens
- Injected workspace or environment context
- Declared tools and tool-definition token cost
- Bundled skills and skill-definition token cost
- MCP and sub-agent declarations, with text-only mentions kept separate

All token counts use the same `tiktoken` encoding, `o200k_base`, so agents are compared
with one counting method.

## Supported agents

| Agent ID | Agent |
| --- | --- |
| `codex` | OpenAI Codex CLI |
| `claude-code` | Anthropic Claude Code |
| `cline` | Cline |
| `cursor-cli` | Cursor CLI |
| `droid` | Droid |
| `github-cli` | GitHub Copilot CLI |
| `grok-cli` | Grok CLI |
| `mistral-vibe` | Mistral Vibe |
| `kilo` | Kilo Code |
| `opencode` | OpenCode |
| `openhands` | OpenHands |
| `openclaw` | OpenClaw |
| `pi` | Pi |
| `hermes` | Hermes Agent |

Run `uv run python -m hibench agents` to see the currently pinned versions and image
tags.

## How it works

1. Create a temporary empty Git repository as the subject workspace.
2. Start a local recorder compatible with the agent's outbound API shape.
3. Run the agent in Docker with a dummy API key and local API base URL.
4. Save captured HTTP requests and return a synthetic completion.
5. Write raw artifacts, a summary, and normalized dashboard tables.

The generated subject workspace avoids contaminating measurements with this repository's
own `AGENTS.md`, README, source files, or local Git state.

## Quickstart

### Prerequisites

- Python 3.13, managed manually or by `uv`
- `uv`
- Docker installed and running

### Run one benchmark

```bash
uv sync
uv run python -m hibench agents
uv run python -m hibench run codex --build --prompt prompts/hi.txt
```

The run command prints the output directory. Inspect the captured artifacts:

```bash
cat runs/<run-id>/summary.json
cat runs/<run-id>/benchmark_result.json
ls runs/<run-id>/requests
```

Replace `codex` with any supported agent ID.

To run a specific agent version:

```bash
uv run python -m hibench run codex \
  --build \
  --version 0.139.0 \
  --run-id codex-0.139.0-hi \
  --replace
```

## Benchmark many versions

`hibench benchmark` refreshes the agent's version catalog, benchmarks missing valid
versions, and refreshes aggregate CSVs in `results/`.

Preview a plan:

```bash
uv run python -m hibench benchmark codex --dry-run
```

Run a small batch:

```bash
uv run python -m hibench benchmark codex --max-versions 5
```

Run every supported agent in one invocation:

```bash
uv run python -m hibench benchmark all --max-versions 1
```

For `all`, `--max-versions` applies per agent.

By default, hibench considers the latest 100 benchmarkable versions, skips stored valid
captures, and removes per-version Docker images after each attempted run. Use
`--version <x>` to target one version, `--rerun-existing` to replace stored captures, or
`--initial-version-limit 0` to disable the latest-version window.

## Outputs

Each run writes:

- `runs/<run-id>/manifest.json`
- `runs/<run-id>/requests/*.json`
- `runs/<run-id>/stdout.txt` and `stderr.txt`
- `runs/<run-id>/summary.json`
- `runs/<run-id>/benchmark_result.json`
- `runs/<run-id>/benchmark_tables/*.csv`

Aggregate dashboard-ready CSVs live in `results/`. Rebuild them manually with:

```bash
uv run python -m hibench export --runs-dir runs --out results
```

Use `run.csv.total_body_tokens` as the comparable total. Diagnostic tables such as
tools, skills, MCP, sub-agents, and text fields can overlap and should not be summed as a
second total.

The repository tracks the aggregate `results/` tables for inspection and dashboard
builds. Raw capture artifacts under `runs/` are local/generated and are intentionally
excluded from source control.

See [`docs/architecture.md`](docs/architecture.md) for capture details, agent-specific
runner notes, version-selection policy, and the full result schema.

## Dashboard

The static dashboard source lives in [`web/`](web/) and reads the aggregate `results/`
tables. The public site is deployed to <https://hibench.dev>, with source available at
<https://github.com/hibenchmark/hibench>.

```bash
cd web
npm ci
npm run build
```

## Development

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q hibench tests main.py
```

## Contributing

Open an issue or pull request with the context needed to reproduce the change. When
adding an agent, include the agent metadata, Docker image, parser coverage, version
catalog support, documentation updates, and a canonical capture when practical.

## License

See [`LICENSE`](LICENSE) for licensing details.
