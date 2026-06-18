---
name: weekly-benchmark-update
description: Run the weekly hibench benchmark and draft the @hibenchmark X update thread from current-vs-last-recorded benchmark findings.
allowed_tools: read,write,shell
---

# Weekly Benchmark Update Mode

Run the weekly hibench benchmark, compare the refreshed latest result for each
agent against that same agent's last recorded benchmark result in
`results/runs.csv`, and draft the @hibenchmark X post thread.

This command is for the recurring weekly public update. It should produce human
analysis, not a mechanical metrics dump.

## Core Rule

Compare **current latest benchmark row vs last recorded benchmark row** for
each agent.

Do **not** compare the latest version to the previous version inside the newly
refreshed aggregate unless that row is also the last recorded benchmark row for
that agent. Do not copy `results/runs.csv` to a temp snapshot. Treat
`results/runs.csv` as the benchmark history: the workflow appends new captured
rows, so the previous comparison point should already be present in that same
file.

If multiple rows were added for one agent during the current run, compare the
current latest row against the last row for that agent that existed before this
weekly run. Use `git diff -- results/runs.csv` or the file's append boundary to
identify that row. If the boundary is unclear, stop and ask instead of
inventing a comparison.

## Workflow

1. Start safely.
   - Read `MEMORY.md` and current `TODO.md` per project protocol.
   - Inspect `git status --short`; note unrelated dirty files.
   - Check whether `results/runs.csv` is already dirty. If it is, ask whether
     those changes belong to the previous baseline or the current weekly run.
   - Add/update `TODO.md` task-list entries for this workflow.

2. Run the benchmark.
   - First dry-run:

     ```bash
     uv run python -m hibench benchmark all --dry-run
     ```

   - If the dry-run is sane and Docker is available, run:

     ```bash
     uv run python -m hibench benchmark all
     ```

   - If Docker is unavailable or the run is blocked, stop and report the block.
     Do not draft a "fresh weekly" post from stale data unless the user
     explicitly asks for a stale-data draft.

3. Refresh exports and OG images.
   - Ensure aggregate results and web OG assets reflect the refreshed runs:

     ```bash
     uv run python -m hibench export --runs-dir runs --out results
     (cd web && npm run build)
     ```

   - Main X image: `web/public/og-image.png`
   - Per-agent reply images: `web/public/og/agents/<agent-id>.png`

4. Analyze current-vs-last-recorded benchmark changes.
   - Use `results/runs.csv` as both the current data source and benchmark
     history. Do not create a temp copy.
   - For each agent, find the latest benchmarkable row after the run and the
     last recorded benchmarkable row for that same agent before the new row(s).
   - For each agent:
     - pick the current latest benchmarkable row
     - pick the last recorded benchmarkable row for the same agent
     - compare tokens and counted surfaces between those two rows
   - If an agent has no previous recorded row, call it new to HiBench.
   - If the same latest version is still the latest recorded row, report no
     latest movement unless aggregate counts changed.
   - Sort the reply draft by current latest `body_tokens`, smallest to largest.

   Useful analysis script skeleton:

   ```bash
   uv run python - <<'PY'
   import csv
   import subprocess
   from pathlib import Path

   current_path = Path("results/runs.csv")

   INT_FIELDS = [
       "body_tokens",
       "system_prompt_tokens",
       "tool_definition_tokens",
       "skills_count",
       "tool_count",
       "mcp_count",
       "subagent_count",
       "skills_tokens",
       "mcp_tokens",
       "subagent_tokens",
   ]

   def load_rows(text):
       rows = list(csv.DictReader(text.splitlines()))
       by_agent = {}
       for row in rows:
           if row.get("has_primary_request") != "True":
               continue
           for field in INT_FIELDS:
               row[field] = int(row[field] or 0)
           by_agent.setdefault(row["agent_id"], []).append(row)
       return by_agent

   # Current data comes from the working tree after the benchmark/export.
   after = load_rows(current_path.read_text(encoding="utf-8"))

   # Prefer the tracked pre-run file as the baseline without copying to temp.
   # If this command is run outside Git, fall back to the prior row in file order.
   try:
       previous_text = subprocess.check_output(
           ["git", "show", "HEAD:results/runs.csv"], text=True
       )
       before = {agent: rows[-1] for agent, rows in load_rows(previous_text).items()}
   except Exception:
       before = {agent: rows[-2] for agent, rows in after.items() if len(rows) > 1}

   latest = {agent: rows[-1] for agent, rows in after.items()}

   for agent_id, row in sorted(latest.items(), key=lambda item: item[1]["body_tokens"]):
       prev = before.get(agent_id)
       print()
       print(agent_id, row["agent_name"], row["agent_version"], row["body_tokens"])
       if not prev:
           print("  new_to_hibench")
           continue
       print("  previous_recorded", prev["agent_version"], prev["body_tokens"])
       print("  token_delta", row["body_tokens"] - prev["body_tokens"])
       for field in ["tool_count", "skills_count", "subagent_count", "mcp_count"]:
           delta = row[field] - prev[field]
           if delta:
               print(" ", field, prev[field], "->", row[field], f"({delta:+})")
       for field in ["system_prompt_tokens", "tool_definition_tokens", "skills_tokens", "subagent_tokens", "mcp_tokens"]:
           delta = row[field] - prev[field]
           if delta:
               print(" ", field, f"{delta:+}")
   PY
   ```

   If `results/runs.csv` was already dirty before the run, do not rely on
   `HEAD:results/runs.csv` until the user confirms that tracked `HEAD` is the
   intended previous benchmark baseline.

5. Draft the X thread.
   - Main post:
     - attach `web/public/og-image.png`
     - mention same setup: empty repo, prompt `Hi`, first model request captured
     - include current totals: agents tracked, captured versions, token range
     - mention new agents or notable top-level benchmark movement
     - include `hibench.dev`
     - include "startup footprint, not a quality score"
   - Replies:
     - one reply per agent
     - attach `web/public/og/agents/<agent-id>.png`
     - focus on the main current-vs-last-recorded benchmark finding
     - keep each reply under 280 characters unless the user asks otherwise
     - do not number replies unless needed for readability

## Writing Style

Use a neutral, finding-led voice.

Good patterns:
- "`<Agent>` moved slightly up/down in this week's benchmark."
- "`<Agent>` is unchanged from the last recorded benchmark."
- "`<Agent>` is new in HiBench this week."
- "The visible change is in `<component>` tokens."
- "Counts stay the same: `<n>` tools, `<n>` skills, `<n>` subagents, `<n>` MCP."
- "The main measured change is `<count>` moving from `<old>` to `<new>`."

Avoid:
- judging quality, speed, usefulness, or architecture
- "best", "worst", "bloated", "quiet", "heavy", "dominates", "workbench",
  "operating environment", "tool-shaped", or similar interpretive language
- listing every metric when only one changed
- saying "latest vs previous version" unless that was also the previous
  recorded benchmark row

Keep the copy human:
- lead with the finding
- include only supporting numbers needed to understand it
- prefer "this week's benchmark" over "the data says"
- avoid CSV/reporting phrasing such as "declares" repeated in every reply

## Validation

Before final handoff, run the smallest useful validation set:

```bash
uv run python -m hibench agents
uv run python -m hibench benchmark all --dry-run
git diff --check
```

If web assets changed, also confirm:

```bash
(cd web && npm run build)
file web/public/og-image.png web/public/og/agents/*.png | head
```

Check draft lengths with a short script or manual character counts. Report any
reply over 280 characters.

## Output Format

Return:

## Weekly Benchmark Update

- benchmark: completed / blocked
- comparison baseline: last recorded rows in `results/runs.csv`
- current results: agents, versions, latest token range
- assets: main OG image and per-agent image pattern

## Main X Post

```text
...
```

## Reply Drafts

For each reply:

- image: `web/public/og/agents/<agent-id>.png`

```text
...
```

## Validation

List commands run and result. If blocked, explain exactly what blocked the run.

## Remaining Risk

Name any stale data, failed captures, missing images, or unclear comparisons.