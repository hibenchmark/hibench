from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkerDimension:
    key: str
    summary_key: str
    label: str
    table_name: str
    run_field_prefix: str
    tool_related_field: str
    declaration_keys: frozenset[str]
    identity_markers: frozenset[str]
    text_markers: frozenset[str]

    @property
    def report_heading(self) -> str:
        return f"{self.label} rows"


MARKER_DIMENSIONS = (
    MarkerDimension(
        key="mcp",
        summary_key="mcp",
        label="MCP",
        table_name="mcp",
        run_field_prefix="mcp",
        tool_related_field="is_mcp_related",
        declaration_keys=frozenset({"mcp", "mcp_server", "mcp_servers"}),
        identity_markers=frozenset({"mcp"}),
        text_markers=frozenset({"mcp"}),
    ),
    MarkerDimension(
        key="subagent",
        summary_key="subagents",
        label="Sub-agent",
        table_name="subagents",
        run_field_prefix="subagent",
        tool_related_field="is_subagent_related",
        declaration_keys=frozenset({"agents", "subagent", "sub_agent", "sub_agents"}),
        identity_markers=frozenset({"subagent", "sub_agent", "sub_agents"}),
        text_markers=frozenset({"multi_agent", "subagent", "sub_agent", "sub_agents"}),
    ),
)
MARKER_DIMENSIONS_BY_KEY = {dimension.key: dimension for dimension in MARKER_DIMENSIONS}
MARKER_DIMENSIONS_BY_SUMMARY_KEY = {
    dimension.summary_key: dimension for dimension in MARKER_DIMENSIONS
}


__all__ = [
    "MARKER_DIMENSIONS",
    "MARKER_DIMENSIONS_BY_KEY",
    "MARKER_DIMENSIONS_BY_SUMMARY_KEY",
    "MarkerDimension",
]
