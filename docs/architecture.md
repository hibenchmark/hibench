# Architecture

hibench captures what a coding agent sends by default before any real model call happens.

## Flow

1. Create a temporary empty Git repository as the subject workspace.
2. Start a local HTTP recorder compatible with the agent's outbound API shape.
3. Run the agent in its pinned Docker image.
4. Point the agent API base URL at the recorder and use a dummy API key.
5. Return a synthetic successful completion after capture, avoiding real upstream calls
   and auth retry noise.
6. Save request payloads, stdout/stderr, manifest metadata, a summary, and normalized
   benchmark tables.
7. When aggregate export is enabled for a single-agent benchmark, refresh
   `results/github_stars.json` for that agent when it has `links.github_repo`
   metadata. GitHub stars are fetched after Anthropic token counting and the aggregate
   dashboard export. `hibench benchmark all` gets the same behavior by delegating to
   the per-agent benchmark workflow.

Agent detail pages read official links from `agents/<agent-id>/agent.json` and read the
latest fetched star counts from `results/github_stars.json`; star counts are generated
metadata, not hard-coded web literals.

## Agent targets

Agent definitions live under `agents/<agent-id>/agent.json`.

Codex is installed in `docker/agents/codex/Dockerfile` with a pinned npm package version.
The runner executes:

```bash
codex exec --json "Hi"
```

inside a generated empty Git repo. This avoids contaminating measurements with hibench's own
`AGENTS.md`, README, or source files.

Claude Code is installed in `docker/agents/claude-code/Dockerfile` with a pinned npm
package version. The runner executes:

```bash
claude -p "Hi" --output-format json
```

inside the same generated empty Git repo. hibench sets `ANTHROPIC_BASE_URL` to the local
recorder root, so Claude Code's Anthropic Messages API requests are captured and answered
with a synthetic completion.

Cline is installed in `docker/agents/cline/Dockerfile` from the official `cline` npm
package. The runner executes:

```bash
cline --json --cwd /workspace --data-dir /cline-home/data --provider openai-compatible --model gpt-5 --key hibench-dummy-key --timeout 20 "Hi"
```

inside the same generated empty Git repo. hibench writes
`/cline-home/data/settings/providers.json` at container startup with an
`openai-compatible` provider whose `baseUrl` points at the local recorder. The container
isolates Cline state under `/cline-home`, disables telemetry/migration notices where
supported, and uses `--data-dir` to force the local runtime path without requiring a
Cline account or upstream model call.

GitHub Copilot CLI is installed in `docker/agents/github-cli/Dockerfile` from the
official `@github/copilot` npm package. The runner executes:

```bash
copilot -p "Hi" --model gpt-5.4 --output-format json --stream off --no-custom-instructions --no-auto-update --no-remote --allow-all-tools
```

inside the same generated empty Git repo. hibench uses Copilot CLI BYOK environment
variables (`COPILOT_PROVIDER_BASE_URL`, `COPILOT_PROVIDER_WIRE_API=responses`, and a
dummy provider key) to point model traffic at the OpenAI Responses-compatible recorder.
`COPILOT_OFFLINE=true` disables GitHub authentication, telemetry, web tools, and remote
control during capture so no GitHub Copilot or upstream model call is required.

Cursor CLI is installed in `docker/agents/cursor-cli/Dockerfile` from Cursor's pinned
release tarball. The runner executes:

```bash
cursor-agent-local -p "Hi" --output-format json --model gpt-5 --authless --trust
```

inside the same generated empty Git repo. Cursor's documented install script installs the
standard `agent-cli` package; inspection of the packaged CLI shows the OpenAI-compatible
`--base-url`/`CURSOR_LOCAL_AGENT_BASE_URL` provider path is hidden and gated to the
companion `agent-cli-local` package from the same release. hibench downloads that local
package directly, sets `CURSOR_ENABLE_AUTHLESS=1`, and points
`CURSOR_LOCAL_AGENT_BASE_URL` plus a dummy provider key at the OpenAI-compatible recorder,
so no Cursor account, Cursor backend, or upstream model call is required.

Devin is installed in `docker/agents/devin/Dockerfile` from Cognition's static CLI
manifest and pinned Linux tarball. The runner executes:

```bash
devin -p "Hi"
```

inside the same generated empty Git repo. hibench writes isolated
`$XDG_DATA_HOME/devin/credentials.toml` and `$XDG_CONFIG_HOME/devin/config.json` at
container startup with a dummy Devin key and API URLs pointed at the local recorder.
Devin sends Connect/protobuf API requests; hibench parses the primary
`ApiServerService/GetChatMessage` payload, while auth/status, telemetry, model-config,
and session-title requests are treated as auxiliary. No Cognition-hosted session or
upstream model call is required.

Droid is installed in `docker/agents/droid/Dockerfile` from Factory's `droid` npm
package. The runner executes:

```bash
droid exec "Hi" --cwd /workspace --model custom:HiBench-Droid-0 --output-format json
```

inside the same generated empty Git repo. hibench writes an isolated
`~/.factory/settings.json` with `cloudSessionSync=false` and a BYOK custom OpenAI
Responses model whose `baseUrl` points at the local recorder. The Docker environment uses
dummy Factory/model keys and disables keyring access, hooks, IDE auto-connect, sounds, and
auto-update so no Factory account, synced session, or upstream model call is required.

Gemini CLI is installed in `docker/agents/gemini-cli/Dockerfile` from Google's
`@google/gemini-cli` npm package. The runner executes:

```bash
gemini -p "Hi" --output-format json --model gemini-2.5-flash
```

inside the same generated empty Git repo. hibench writes isolated
`~/.gemini/settings.json` at container startup to select Gemini API key auth, disable
telemetry/autoupdate, and trust only the generated benchmark workspace. The Docker
environment sets a dummy `GEMINI_API_KEY` and points `GOOGLE_GEMINI_BASE_URL` at the
local recorder root, which captures Gemini `generateContent`/`streamGenerateContent`
traffic and returns a synthetic Gemini-shaped response. For Gemini CLI versions that
require localhost for non-HTTPS custom base URLs, hibench maps container `localhost` to
Docker's host gateway for this agent. No Google account, Gemini API key, or upstream
model call is required.

Grok CLI is installed in `docker/agents/grok-cli/Dockerfile` from the official
`@xai-official/grok` npm package. The runner executes:

```bash
grok --no-auto-update -p "Hi" -m hibench --output-format json --no-alt-screen --max-turns 1
```

inside the same generated empty Git repo. hibench writes an isolated
`~/.grok/config.toml` at container startup. The config sets permission mode to
`always-approve` and defines a custom model with `base_url` pointed at the local
OpenAI-compatible recorder and `env_key` pointed at `HIBENCH_GROK_API_KEY`, a dummy
benchmark key. Newer Grok versions may send a session-title chat completion before the
agent request; hibench treats that as auxiliary and selects the main chat completion as
the primary benchmark request.

Kilo Code is installed in `docker/agents/kilo/Dockerfile` from the official
`@kilocode/cli` npm package. The runner executes:

```bash
kilo run --format json --title hibench --model hibench/gpt-5 "Hi"
```

inside the same generated empty Git repo. hibench passes `KILO_CONFIG_CONTENT` with a
custom OpenAI-compatible provider whose `baseURL` points at the local recorder. The
container isolates Kilo state under `/kilo-home`, disables the local daemon, model
fetching, autoupdate, and LSP downloads, and uses an in-memory DB for repeatable
one-shot captures.

OpenCode is installed in `docker/agents/opencode/Dockerfile` with a pinned npm package
version. The runner executes:

```bash
opencode run --format json --title hibench --model hibench/gpt-5 "Hi"
```

inside the same generated empty Git repo. hibench passes `OPENCODE_CONFIG_CONTENT` with
a custom OpenAI-compatible provider whose `baseURL` points to the local recorder.

Pi is installed in `docker/agents/pi/Dockerfile` using Bun with `--ignore-scripts`.
Versions before `0.74.0` install the legacy `@mariozechner/pi-coding-agent` npm package;
`0.74.0+` installs `@earendil-works/pi-coding-agent`. The runner executes:

```bash
pi -p --provider hibench --model gpt-5 --no-session "Hi"
```

inside the same generated empty Git repo. hibench writes `models.json` at container
startup with a custom OpenAI-compatible provider whose `baseUrl` points to the local
recorder. The explicit `--provider` is required by older Pi releases that did not yet
interpret `--model provider/model` references.

Hermes Agent is installed in `docker/agents/hermes/Dockerfile` from the `hermes-agent`
PyPI package. The runner executes:

```bash
hermes --provider hibench --model gpt-5 -z "Hi"
```

inside the same generated empty Git repo. hibench writes a clean `config.yaml` under an
isolated `HERMES_HOME` with a custom OpenAI-compatible provider whose `api` points to the
local recorder. The config pins context length and disables live model discovery so
Hermes does not send preflight model-probe POSTs before the generation request.

Mistral Vibe is installed in `docker/agents/mistral-vibe/Dockerfile` from the
`mistral-vibe` PyPI package. The runner executes:

```bash
vibe -p "Hi" --max-turns 1 --output json --trust
```

inside the same generated empty Git repo. hibench writes a clean `config.toml` under an
isolated `VIBE_HOME` with a generic OpenAI-compatible provider whose `api_base` points
to the local recorder. Telemetry, update checks, connectors, and remote Vibe Code are
disabled so no Mistral account, Mistral backend, or upstream model call is required.

OpenHands is installed in `docker/agents/openhands/Dockerfile` from the `openhands`
PyPI package. The runner executes:

```bash
openhands --headless --json --override-with-envs -t "Hi"
```

inside the same generated empty Git repo. hibench sets `LLM_API_KEY`,
`LLM_BASE_URL`, and `LLM_MODEL=openai/gpt-5`, and uses OpenHands' documented env
override flag so model traffic goes to the local OpenAI Responses-compatible recorder.
OpenHands state and XDG paths are isolated under `/openhands-home`, so no OpenHands
Cloud account, saved settings, or upstream model call is required.

## Version automation

`hibench versions <agent-id> --refresh` fetches the configured npm or PyPI version
list, merged npm lists for agents that renamed packages, Cursor's current install
script release, or a static current manifest such as Devin's CLI manifest, and stores it
in `agent_versions/<agent-id>.json`.

`hibench benchmark <agent-id>` uses that catalog to run one canonical benchmark per
selected agent version. The catalog still stores every npm version, but each agent selects
only comparable benchmark versions by default. Codex uses plain `X.Y.0` stable main
releases; Claude Code, Cline, Devin, Droid, Gemini CLI, GitHub Copilot CLI, Grok CLI,
Kilo Code, OpenCode, OpenHands, OpenClaw, Pi, Hermes, and Mistral Vibe use plain stable
semver releases such as `2.1.177`, `3.0.24`, `2026.7.23`, `0.153.1`, `0.47.0`,
`1.0.62`, `0.2.51`, `7.3.45`, `1.17.5`, `1.16.0`, `2026.6.6`, `0.79.3`, `0.16.0`, and `2.16.1`; Cursor CLI uses the install
script's timestamped release as-is because Cursor does not publish an npm/PyPI-style
historical package catalog for the CLI tarballs. The stable policies exclude
prereleases, platform/system variants like `*-linux-x64`, and timestamp/internal builds.
The canonical run id is:

```text
<agent-id>-<version>-<prompt-name>
```

Agent metadata can also define one-off `benchmark_exclusions` for published versions that
are not runnable in the benchmark container. Codex `0.54.0` is excluded because its npm
package was published with bad Linux MUSL binaries and fails during Docker image build.

Automatic batches are intentionally limited to the latest 100 benchmarkable versions
before stored runs are skipped. This keeps broad catalogs manageable while still focusing
on recent behavior. The limit can be tuned with `--initial-version-limit` or disabled with
`--initial-version-limit 0`.

Automatic benchmark batches select only missing `agent_id + version` rows by default, so
re-running `hibench benchmark codex --max-versions 1` advances to the next unbenchmarked
version instead of replacing the oldest stored run. Explicit `--version` requests and
`--rerun-existing` can still replace stored versions. Before replacement, the new capture
is staged in a temporary directory; after success, old run directories for the same
agent/version are removed and the staged result is moved into `runs/`. Non-dry-run
benchmark batches then refresh the aggregate `results/` tables after each completed
version, so dashboard inputs update during long loops. The export also de-duplicates source
runs by `agent_id + agent_version`, preferring valid primary-request captures and then the
newest run, so dashboard inputs stay unique even if old timestamped runs remain.

## Current metrics

- captured request count
- request body bytes/chars
- request tokens counted with `tiktoken`
- text-field tokens counted with `tiktoken`
- instruction tokens split by root `instructions`, developer-role injections, and injected
  user/environment context
- injected skills and per-skill definition tokens
- tokenizer metadata for the fixed benchmark encoding and captured request model
- declared tool count and names from `tools` arrays
- counted MCP/sub-agent declarations, with text mentions kept separate

All agents and models use `tiktoken` with `o200k_base` for token counting so results
share one calculation method.

## Dashboard result model

Power BI and docs dashboards should use the normalized `hibench.benchmark.v1` output:

- `benchmark_result.json`: one JSON object with `run`, `tools`, `mcp`, `subagents`, and
  `text_fields` arrays.
- `benchmark_tables/run.csv`: one wide row per run/agent/version.
- `benchmark_tables/tools.csv`: one row per tool with `definition_tokens`.
- `benchmark_tables/skills.csv`: one row per injected skill with `definition_tokens`.
- `benchmark_tables/mcp.csv`: one row per MCP declaration or text mention with `tokens`.
- `benchmark_tables/subagents.csv`: one row per sub-agent declaration or text mention with `tokens`.
- `benchmark_tables/text_fields.csv`: one row per prompt/context text field.

`hibench benchmark` refreshes aggregate CSVs automatically after each completed version. Use
`uv run python -m hibench export --runs-dir runs --out results` when you need to rebuild
them manually.

Dimension tables can overlap: for example an MCP mention may be inside a skills block or a
tool description. Use `run.total_body_tokens` as the comparable total.

Important run columns:

- `total_body_tokens`: full primary request body tokens.
- `has_primary_request`: filter to valid first-payload comparisons.
- `system_prompt_tokens`: system/developer instruction text.
- `environment_context_tokens`: injected environment/workspace context.
- `user_prompt_tokens`: the literal test prompt.
- `main_instructions_tokens`, `developer_instructions_tokens`,
  `injected_user_context_tokens`: source-level instruction split.
- `skills_count`, `skills_tokens`, `skill_definition_tokens`: injected skill surface.
- `default_context_tokens`: system prompt + environment context + tool definitions.
- `tool_count`, `tool_definition_tokens`.
- `mcp_count`, `subagent_count`: counted declarations only.
- `mcp_mention_count`, `subagent_mention_count`: uncounted diagnostic mentions.