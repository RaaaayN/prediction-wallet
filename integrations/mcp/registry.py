"""Capability registry for MCP toolsets."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from pydantic_ai.mcp import MCPServerStdio

from config import MCP_TIMEOUT_SECONDS


@dataclass(frozen=True)
class MCPProfile:
    name: str
    description: str
    command: str
    args: tuple[str, ...]


class ToolCapabilityRegistry:
    """Resolve configured MCP profiles into toolsets for Pydantic AI."""

    def __init__(self):
        server_module = "integrations.mcp.server"
        self._profiles = {
            "local": MCPProfile(
                name="local",
                description="Local MCP market data tools",
                command=sys.executable,
                args=("-m", server_module),
            )
        }

    def available_profiles(self) -> list[dict]:
        return [{"name": p.name, "description": p.description} for p in self._profiles.values()]

    def build_toolsets(self, profile_name: str | None):
        if not profile_name or profile_name == "none":
            return []
        profile = self._profiles.get(profile_name)
        if profile is None:
            raise ValueError(f"Unknown MCP profile '{profile_name}'.")
        return [
            MCPServerStdio(
                command=profile.command,
                args=list(profile.args),
                cwd=os.getcwd(),
                timeout=MCP_TIMEOUT_SECONDS,
                read_timeout=60,
                tool_prefix=f"{profile.name}_",
            )
        ]
