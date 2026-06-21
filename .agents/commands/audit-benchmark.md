---
name: audit-benchmark
description: Audit a hibench run or request for parser, capture, and aggregate-data correctness.
allowed_tools: read,shell,sub-agent
---

# Benchmark Audit Mode

Audit one hibench benchmark run, request file, or agent/version row. Treat this as a read-only investigation.

Use this command when the user asks to audit, inspect, verify, or sanity-check benchmark artifacts such as:
- `runs/<run-id>/requests/<nnnn>.json`
- `runs/<run-id>/summary.json`
- `runs/<run-id>/benchmark_result.json`
- `runs/<run-id>/benchmark_tables/*.csv`
- aggregate rows in `results/*.csv`
- parser behavior in `hibench/parsers/<parser>.py`
- agent/version exclusion policy in `agents/<agent-id>/agent.json` or `agent_versions/<agent-id>.json`

## Mission

Determine whether the stored benchmark data faithfully represents the raw model request.

Answer these questions:
- Is the primary request correct and comparable?
- Are source text fields classified correctly?
- Are actual user prompt tokens separated from injected context?
- Are skills, tools, MCP declarations, and subagent declarations counted correctly?
- Are prose mentions tracked as mentions only, not declarations?
- Are descriptions complete, with only `preview` fields intentionally cropped?
- Do run-level CSV totals match the parsed summary?
- Do aggregate `results/` rows include or exclude the run as expected?
- Should the version be excluded from default benchmarks because the capture is non-comparable?

## Workflow

Start with narrow evidence and widen only as needed.

1. Identify the run.
   - If given a request path, derive `run_dir` from it.
   - Read `manifest.json`, `summary.json`, and `benchmark_result.json` if present.
   - Note `agent_id`, `agent_version`, `parser_id`, `request_count`, `primary_request_index`, request method/path, model, process exit, and timeout status.

2. Inspect the raw request.
   - Read the target `requests/<nnnn>.json`.
   - Parse `json` body shape: top-level keys, model, input/messages/system/instructions/tools.
   - Identify preflight or auxiliary requests such as title generation, count-tokens, model discovery, HEAD checks, or session setup.
   - Confirm whether the selected request is the real generation request for the user prompt.

3. Compare text classification.
   - List every parsed text field: path, role, category, source, token count, preview.
   - Verify important categories:
     - `main_instructions`
     - `developer_instructions`
     - `permissions_instructions`
     - `skills_instructions`
     - `injected_user_context`
     - `user_prompt`
     - `assistant_context`
     - `tool_context`
   - Check that environment wrappers such as `<environment_context>`, `<system-reminder>`, `<user_info>`, `<git_status>`, or current-date context are not counted as the user's prompt.

4. Compare skills.
   - Inspect the raw skill inventory section.
   - Count real skill entries from the raw request.
   - Compare against `benchmark_tables/skills.csv`.
   - Verify `skill_name`, `skill_file`, `source_path`, definition chars/tokens, and full `description`.
   - Treat the `preview` column as intentionally cropped unless the full `description` is also cropped.
   - Watch for parser bugs:
     - entries before the actual skills list miscounted as skills
     - continuation lines omitted from descriptions
     - XML skills missed
     - prose references to skills counted as declarations

5. Compare tools.
   - Count raw tool definitions.
   - Compare against `benchmark_tables/tools.csv`.
   - Verify tool identity extraction for function, custom, hosted, MCP, search, and agent/subagent tools.
   - Confirm tool token totals match summary.

6. Compare MCP and subagents.
   - Separate declarations from text mentions.
   - Count declarations only when the request declares actual MCP servers/tools or subagent/agent types.
   - Treat plain prose such as "MCP", "subagent", "multi-agent", or "tool discovery" as mention rows unless accompanied by declarations.
   - Verify `is_counted` and run-level `*_count`, `*_tokens`, `*_mention_count`, and `*_mention_tokens`.

7. Recompute when useful.
   - Use `uv run python` for any script importing project modules.
   - Recompute with `summarize_request(..., parser_id=<parser>)` and compare key saved values.
   - Byte-cap shell output. Prefer small Python summaries over dumping full JSON.

8. Check aggregate data.
   - Search `results/runs.csv`, `results/skills.csv`, `results/tools.csv`, `results/mcp.csv`, `results/subagents.csv`, and `results/text_fields.csv` for the run/version.
   - Confirm aggregate rows match per-run benchmark tables.
   - If the run is invalid and the user asked to clean data, recommend or perform the standard cleanup:
     - add a reasoned `benchmark_exclusions` entry
     - update `agent_versions/<agent-id>.json`
     - remove the canonical run directory
     - run `uv run python -m hibench export --runs-dir runs --out results`

## Useful Commands

Use focused commands like these, adjusting paths:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from hibench.analyze import summarize_request

run = Path("runs/<run-id>")
request = json.loads((run / "requests" / "0001.json").read_text())
saved = json.loads((run / "summary.json").read_text())["primary_request"]
current = summarize_request(request, parser_id="<parser-id>")

checks = [
    ("body_tokens", current["body_tokens"], saved["body_tokens"]),
    ("text_tokens", current["text_fields"]["tokens"], saved["text_fields"]["tokens"]),
    ("skills_count", current["skills"]["count"], saved["skills"]["count"]),
    ("tool_count", current["tools"]["count"], saved["tools"]["count"]),
    ("mcp_count", current["mcp"]["count"], saved["mcp"]["count"]),
    ("subagent_count", current["subagents"]["count"], saved["subagents"]["count"]),
]
for name, current_value, saved_value in checks:
    print(name, current_value, saved_value, current_value == saved_value)
PY
```

```bash
uv run python - <<'PY'
import csv
from pathlib import Path

run_id = "<run-id>"
for path in Path("results").glob("*.csv"):
    rows = [row for row in csv.DictReader(path.open()) if row.get("run_id") == run_id]
    print(path, len(rows))
PY
```

## Finding Standards

Call something a parser/capture issue only when raw request evidence proves the saved benchmark data is wrong or non-comparable.

Common findings:
- **Parser bug:** raw request contains full data but parser omits, merges, misclassifies, or overcounts it.
- **Capture issue:** run captured an auxiliary/preflight request as primary, captured setup noise, timed out before primary request, or routed through an unintended provider/model.
- **Data issue:** per-run artifacts are correct but aggregate `results/` is stale or includes excluded/no-primary rows.
- **Policy issue:** version should be excluded because its shape cannot be made comparable under current harness constraints.
- **No issue:** raw request, parser output, run tables, and aggregate rows all align.

## Output Format

Return:

## Benchmark Audit

- `target`: run/request audited
- `agent`: `<agent_id> <agent_version>`
- `primary request`: method/path/model/index
- `verdict`: `clean` | `parser issue` | `capture issue` | `data issue` | `policy exclusion recommended`

## Evidence

List the concrete raw-request and artifact evidence. Include counts for text fields, skills, tools, MCP, and subagents.

## Findings

If issues exist, list each with:
- title
- evidence
- impact on benchmark counts or comparability
- recommended fix

If no issues, write `No findings.`

## Validation

List recomputation, CSV checks, tests, or commands run. If validation was skipped, say why.

## Next Step

Give the single most useful next action, such as:
- no action
- patch parser
- regenerate run artifacts
- refresh aggregate `results/`
- add version exclusion and remove run data