"""Subprocess runner with async SSE streaming for CLI commands."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator

PROJECT_ROOT = Path(__file__).parent.parent


async def stream_command(args: list[str], env_extras: dict | None = None) -> AsyncIterator[str]:
    import os

    env = os.environ.copy()
    if env_extras:
        env.update(env_extras)

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        yield f"data: {json.dumps({'line': line})}\n\n"

    await proc.wait()
    yield f"data: {json.dumps({'exit': proc.returncode})}\n\n"


def build_cycle_args(
    step: str,
    strategy: str = "threshold",
    mode: str = "simulate",
    mcp: str = "none",
    profile: str | None = None,
) -> list[str]:
    args = ["main.py", step, "--strategy", strategy, "--mode", mode, "--use-mcp", mcp]
    if profile:
        args += ["--profile", profile]
    return args
