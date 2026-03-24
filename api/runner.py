"""Subprocess runner with async SSE streaming for CLI commands.

Uses run_in_executor + subprocess.Popen so it works on Windows where
asyncio.create_subprocess_exec requires ProactorEventLoop, which uvicorn
does not provide by default.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator

PROJECT_ROOT = Path(__file__).parent.parent

# Sentinel placed in the queue by the reader thread when the process exits.
_DONE = object()


def _run_and_enqueue(
    cmd: list[str],
    env: dict,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Blocking worker: runs the subprocess and pushes lines into the queue.

    Executed inside a ThreadPoolExecutor so the event loop is never blocked.
    Each item placed on the queue is either a ``str`` line or the ``_DONE``
    sentinel carrying the integer return code as a second element.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        loop.call_soon_threadsafe(queue.put_nowait, line)
    proc.wait()
    loop.call_soon_threadsafe(queue.put_nowait, (_DONE, proc.returncode))


async def stream_command(args: list[str], env_extras: dict | None = None) -> AsyncIterator[str]:
    import os

    env = os.environ.copy()
    if env_extras:
        env.update(env_extras)

    cmd = [sys.executable] + args
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    # Launch the blocking subprocess reader in a thread pool so the event loop
    # is free to handle other requests while we wait for output.
    loop.run_in_executor(None, _run_and_enqueue, cmd, env, queue, loop)

    while True:
        item = await queue.get()
        if isinstance(item, tuple) and item[0] is _DONE:
            yield f"data: {json.dumps({'exit': item[1]})}\n\n"
            break
        yield f"data: {json.dumps({'line': item})}\n\n"


def build_cycle_args(
    step: str,
    strategy: str = "threshold",
    mode: str = "simulate",
    profile: str | None = None,
) -> list[str]:
    args = ["main.py", step, "--strategy", strategy, "--mode", mode]
    if profile:
        args += ["--profile", profile]
    return args
