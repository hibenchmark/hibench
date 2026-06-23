---
name: hibench-communication
description: >
  Draft public HiBench communications for @hibenchmark, especially X launch
  posts and weekly benchmark update threads with neutral finding-led analysis.
  Use when writing or editing HiBench social posts, weekly update copy, or
  benchmark-result communication style.
---

# HiBench Communication

## Purpose

Write public-facing HiBench posts that explain benchmark findings without
judging agent quality.

HiBench's core public framing:

> Coding agents do work before they answer. HiBench measures the default
> startup footprint: context, tools, skills, MCP, and subagents.

Canonical method line:

> Empty repo. Prompt: `Hi`. First model request captured.

Canonical caveat:

> Startup footprint, not a quality score.

## Voice

Use a neutral, finding-led, human voice.

Prefer:
- "this week's benchmark"
- "captured at `<n>` tokens"
- "moved slightly up/down"
- "unchanged from the last recorded benchmark"
- "new in HiBench this week"
- "the visible change is in `<component>`"
- "counts stay the same"
- "current vs last recorded benchmark"

Avoid:
- judging quality, architecture, usefulness, speed, or privacy
- "best", "worst", "bloated", "quiet", "heavy", "dominates"
- "workbench", "operating environment", "tool-shaped", "prompt-shaped"
- robotic repeats like "declares ..." in every reply
- full metric dumps when one finding is enough

## Data Rule

For weekly update analysis, compare:

**current latest benchmark row vs the same agent's last recorded benchmark row**

Do not compare against the previous package version unless that row is also the
last recorded benchmark row. If the baseline is unclear, ask before drafting.

Use exact values from `results/runs.csv` and current generated assets. Do not
say "fresh run" unless the benchmark actually ran.

For the end-to-end workflow, use `/weekly-benchmark-update`; this skill governs
the writing style and post structure.

## Main X Post Format

Attach: `web/public/og-image.png`

Target: short, conversational, not a report header.

Pattern:

```text
Weekly HiBench #[n] is out.

Same setup for every coding agent: empty repo, prompt "Hi", first model request captured.

[agents] agents, [versions] versions. Latest first requests range from [min] to [max] tokens.

[Notable new agent or top-level finding.]

Startup footprint, not a quality score.

hibench.dev
```

Keep the main post focused on:
- method
- total coverage
- latest token range
- new agents or one major top-level movement
- caveat and link

## Reply Post Format

Attach one per-agent image:

`web/public/og/agents/<agent-id>.png`

Sort replies by current latest `body_tokens`, smallest to largest, unless user
requests another story order.

Each reply should:
1. Lead with the main finding.
2. Name current version and token count.
3. Compare with the last recorded benchmark row.
4. Mention count/component changes only when they explain the finding.
5. Stay under 280 characters for X unless user asks for longer.

Do not number replies unless the user asks or the platform context needs it.

## Reply Templates

Unchanged:

```text
<Agent> is unchanged from the last recorded benchmark.

<Version> captures at <tokens> tokens, matching <baseline version>. Counts stay the same: <tools> tools, <skills> skills, <subagents> subagents, <mcp> MCP.
```

Small token movement:

```text
<Agent> moved slightly <up/down> in this week's benchmark.

<Version> captures at <tokens> tokens, <+/-delta> vs <baseline version>. The visible change is in <component> tokens; counted surfaces stay the same.
```

Structural/count movement:

```text
<Agent>'s main measured change is <surface> count.

<Version> is <+/-delta> tokens vs the last recorded benchmark, while <surface> moves from <old> to <new>.
```

New agent:

```text
<Agent> is new in HiBench this week.

Latest captured release: <version>, at <tokens> tokens. Counts: <tools> tools, <skills> skills, <subagents> subagents, <mcp> MCP.

This becomes the baseline for future weekly comparisons.
```

## Editing Checklist

Before final copy:
- every numeric claim has a source in current results
- "not a quality score" appears in the main post or first reply
- no judgmental/tool-review language remains
- no reply reads like a CSV row
- per-agent image path is listed beside each reply
- X drafts are character-checked

## Post Example

---
Claude Code 2.1.186 adds a new tool: SendMessage.

Diff vs 2.1.185:
• Default Context : 34,221 tokens (+448)
• Tool count: 26 → 27
• Skills: 13 
• Subagents: 5

Claude Code 2.1.186 ranks #1 out of 16 on our benchmark.

Anthropic is continuing to expand the agent tool surface, with SendMessage now joining the toolbox.
---
Gemini CLI is new in HiBench.

100 versions captured, from 0.11.0 through 0.47.0. Latest release ranks #11 of 16 by startup footprint: 13,789 tokens (Anthropic tokenizer) / 8,465 tokens (o200k tokenizer).

Counts: 8 tools, 2 skills, 3 subagents, 0 MCP.

Startup footprint, not a quality score.
