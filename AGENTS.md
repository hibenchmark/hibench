# AGENTS.md

This file gives coding agents project-specific context and instructions.
Treat it like a README for agents: keep it concise, accurate, and updated
when project workflows change.

## Workspace Snapshot

- Project: **hibench**, an open-source benchmark for coding-agent default footprint.
- Goal: show users how much default context, tool surface, skill surface, MCP surface, and sub-agent surface each coding agent brings before/around a simple prompt such as `Hi`.
- Current stack: small Python CLI, Python 3.13 target, `uv` for dependency management, `tiktoken` with fixed `o200k_base` token counts, one Docker image per tested coding agent.
- Capture model: run an agent in Docker inside a generated empty Git repo, point it at a local recorder with a dummy API key, capture the first outbound request, return a synthetic OpenAI/Anthropic/Gemini-compatible success, and avoid real upstream model calls.
- Current state: supported targets are Codex CLI (`agents/codex/agent.json`, `docker/agents/codex/Dockerfile`, `agent_versions/codex.json`), Claude Code (`agents/claude-code/agent.json`, `docker/agents/claude-code/Dockerfile`, `agent_versions/claude-code.json`), Cline (`agents/cline/agent.json`, `docker/agents/cline/Dockerfile`, `agent_versions/cline.json`), Cursor CLI (`agents/cursor-cli/agent.json`, `docker/agents/cursor-cli/Dockerfile`, `agent_versions/cursor-cli.json`), Devin (`agents/devin/agent.json`, `docker/agents/devin/Dockerfile`, `agent_versions/devin.json`), Droid (`agents/droid/agent.json`, `docker/agents/droid/Dockerfile`, `agent_versions/droid.json`), Gemini CLI (`agents/gemini-cli/agent.json`, `docker/agents/gemini-cli/Dockerfile`, `agent_versions/gemini-cli.json`), GitHub Copilot CLI (`agents/github-cli/agent.json`, `docker/agents/github-cli/Dockerfile`, `agent_versions/github-cli.json`), Grok CLI (`agents/grok-cli/agent.json`, `docker/agents/grok-cli/Dockerfile`, `agent_versions/grok-cli.json`), Kilo Code (`agents/kilo/agent.json`, `docker/agents/kilo/Dockerfile`, `agent_versions/kilo.json`), OpenCode (`agents/opencode/agent.json`, `docker/agents/opencode/Dockerfile`, `agent_versions/opencode.json`), OpenHands (`agents/openhands/agent.json`, `docker/agents/openhands/Dockerfile`, `agent_versions/openhands.json`), OpenClaw (`agents/openclaw/agent.json`, `docker/agents/openclaw/Dockerfile`, `agent_versions/openclaw.json`), Pi (`agents/pi/agent.json`, `docker/agents/pi/Dockerfile`, `agent_versions/pi.json`), Hermes Agent (`agents/hermes/agent.json`, `docker/agents/hermes/Dockerfile`, `agent_versions/hermes.json`), and Mistral Vibe (`agents/mistral-vibe/agent.json`, `docker/agents/mistral-vibe/Dockerfile`, `agent_versions/mistral-vibe.json`).
- Current outputs: runs write raw artifacts plus tokenizer-backed `summary.json`, dashboard-ready `benchmark_result.json`, and `benchmark_tables/*.csv`; aggregate dashboard CSVs plus generated GitHub star metadata (`results/github_stars.json`) live in `results/`.
- Automation: `hibench benchmark <agent-id>` refreshes the configured source catalog by default (npm/PyPI/Cursor install script/static manifest), benchmarks only missing versions selected by the agent's policy within the latest-100 default window, writes one canonical run per version (`runs/<agent-id>-<version>-hi`), counts Anthropic totals when configured, refreshes GitHub stars for agents with `links.github_repo`, and refreshes aggregate `results/`; explicit `--version`/`--rerun-existing` can replace stored runs; prerelease/platform/system/timestamp variants are stored but skipped by default except agents that explicitly use `all_versions`; use `--initial-version-limit 0` to disable the window.
- Reporting model: `hibench.benchmark.v1` uses one run row plus tool/skill/MCP/subagent/text-field fact rows; aggregate export is unique by `agent_id + agent_version`; MCP/subagent counts are declarations only, with text mentions tracked separately.
- Next likely work: extend dashboard/reporting views, rerun existing captures as needed, then add more agents.

## New Agent Implementation Checklist

- Research upstream install/auth/provider docs first. Identify the package/source, a stable latest pin, the CLI invocation for a one-shot `Hi`, and a no-auth/BYOK/local-provider path that can route model traffic to `{base_url}` with dummy credentials and no real upstream calls.
- Add `agents/<agent-id>/agent.json`: lowercase id, display name, pinned version/image, `dockerfile`, `parser_id`, `version_source`, `benchmark_version_policy`, version build arg, `{prompt}` command, local-recorder env, isolated HOME/cache/config env, `capture` notes/timeouts, public `links.official_url`/optional `links.github_repo`, docs `sources`, and reasoned `benchmark_exclusions` for incompatible versions.
- Add `docker/agents/<agent-id>/Dockerfile`: keep OS/runtime/tool layers before the version `ARG`, install the pinned package after that `ARG`, isolate agent state under an agent-specific home, disable color/autoupdate/telemetry where possible, and verify `<cli> --version`. Prefer the shared Bun pattern for npm CLIs and `uv pip install --system` for PyPI CLIs.
- Wire analysis: add a parser in `hibench/parsers/` when generic parsing is not enough, register it in `hibench/parsers/__init__.py`, reuse shared helpers for chat roles or `<available_skills>`, and add analyzer tests for real request shapes plus tool/skill/MCP/subagent declarations.
- Build the version catalog with `uv run python -m hibench versions <agent-id> --refresh`. Probe the latest and earliest selected versions; if older releases reject flags, miss custom provider support, call auth, or produce no primary request, raise the benchmark floor with explicit exclusions in both metadata and `agent_versions/<agent-id>.json`.
- Capture one canonical latest run: `uv run python -m hibench build <agent-id> --version <version>`, `uv run python -m hibench run <agent-id> --version <version> --run-id <agent-id>-<version>-hi --replace`, then `uv run python -m hibench export --runs-dir runs --out results`. Use `benchmark <agent-id> --max-versions 1 --dry-run` and a temp run to verify default selection hits the intended compatible floor.
- Update documentation and UI surfaces: README supported-agent/version sections, `docs/architecture.md` command/env notes, web display-name/logo data in `web/src/data/benchmark-core.js`, and a matching per-agent theme in `web/src/components/AgentTokenRanking.astro` (`bar`, badge, glow, label, and shadow values should fit the existing deep-ink/signal-cyan/amber dashboard style and preserve fallback themes), plus agent/Dockerfile tests, version override tests, and any dashboard aggregate artifacts under `results/`.
- Validate before handoff: `uv run python -m hibench agents`, focused version/catalog assertions, relevant `unittest` modules or full discovery, `uv run python -m compileall -q hibench tests main.py`, `uv run ruff check .`, `uv lock --check`, `npm run build` in `web/` when web/results changed, and `git diff --check`.

## Task Memory Protocol

- Use a single `MEMORY.md` file for both durable memory and recent task history.
- Keep `MEMORY.md` in three sections only: `Metadata`, `Long-Term Memory`, and `Detailed Task Events`.
- At the start of substantive work, read `Metadata`, `Long-Term Memory`, and any current-day detailed entries relevant to the task.
- Keep `Long-Term Memory` compact and edited in place. Store only durable facts: stable repo conventions, important decisions, reusable validation patterns, active follow-ups, and artifacts that matter beyond one task.
- Keep `Detailed Task Events` append-only within the active day. Group entries under one `## YYYY-MM-DD` heading per day.
- After each implementation, append one short task entry to the current day with only: what changed, validation, and next context if needed.
- On the first substantive task of a new day, compact the previous day's detailed entries before appending new ones.
- During compaction, first review every prior-day detailed entry and explicitly write a compact resume of its durable outcome into `Long-Term Memory` before deleting the dated section. Do not delete a prior-day section unless its durable facts, decisions, validation patterns, and unresolved follow-ups have been promoted or consciously deemed non-durable.
- Carry unresolved items into an active/open follow-up bullet if still relevant, then remove prior-day detail that is no longer needed.
- Avoid duplicating long-term bullets. Merge with existing bullets when the fact already exists.
- Keep the file token-efficient: prefer short bullets, avoid command noise, and do not preserve obsolete troubleshooting detail once compacted.

## Session TODO Protocol

- Use `TODO.md` for the current task session only.
- Create or reset `TODO.md` before starting substantive work.
- Use GitHub task-list bullets for every TODO entry: `- [ ]` pending, `- [>]` in progress, `- [x]` done, `- [!]` blocked, `- [-]` dropped.
- Update `TODO.md` as you work. Mark steps complete when they finish, and revise the list when scope changes.
- If TODO.md contains a completed task list, reset it before adding new changes. If it contains an unfinished list, append new `- [ ] ...` tasks instead of writing plain paragraphs.

## Command Output

Protect context usage. **Any command with unknown or potentially large output must be byte-capped.**

## Communication

Before editing, state the approach only for non-trivial tasks.

During complex work, keep updates very short:

- what was found
- what changed
- what risk remains

After work, summarize:

- what changed
- files touched
- validation run, or why skipped
- remaining risk
- next logic steps

Keep summaries short. Do not explain obvious edits.

Oververbosity:low

## Common Commands

- Use `uv` for library management and `uv run python -m hibench ...` for CLI execution.
- uv run for running commands
- uv run ruff check .
- uv run ruff format .
- Use the gh CLI for GitHub work; do not call the GitHub API with curl.
- Prefer gh ... --json ... for pr view / issue view; plain gh pr view and gh issue view can fail here because of the deprecated projectCards query.