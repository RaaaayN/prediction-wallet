"""In-process notebook kernel sessions with shared state across cells."""

from __future__ import annotations

import asyncio
import logging
import io
import threading
import warnings
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotebookKernelSession:
    kernel_id: str
    globals: dict[str, Any] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    execution_count: int = 0

    def __post_init__(self) -> None:
        self.globals.setdefault("__name__", "__main__")
        self.globals.setdefault("__builtins__", __builtins__)

    def execute(self, cells: list[dict[str, Any]]):
        with self.lock:
            for cell_index, cell in enumerate(cells):
                if str(cell.get("type", "code")) != "code":
                    continue

                self.execution_count += 1
                source = str(cell.get("content", ""))
                yield {
                    "kind": "cell_start",
                    "cell_index": cell_index,
                    "execution_count": self.execution_count,
                    "line": f"Running cell {cell_index + 1}",
                }

                stdout = io.StringIO()
                stderr = io.StringIO()
                try:
                    previous_logging_disable = logging.root.manager.disable
                    try:
                        logging.disable(logging.CRITICAL)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            with redirect_stdout(stdout), redirect_stderr(stderr):
                                exec(compile(source, f"<notebook:{self.kernel_id}:cell{cell_index + 1}>", "exec"), self.globals)
                    finally:
                        logging.disable(previous_logging_disable)
                except Exception:
                    stdout_value = stdout.getvalue().splitlines()
                    stderr_value = stderr.getvalue().splitlines()
                    for line in stdout_value:
                        yield {
                            "kind": "stdout",
                            "cell_index": cell_index,
                            "execution_count": self.execution_count,
                            "line": line,
                        }
                    for line in stderr_value:
                        yield {
                            "kind": "stderr",
                            "cell_index": cell_index,
                            "execution_count": self.execution_count,
                            "line": line,
                        }
                    for line in traceback.format_exc().splitlines():
                        yield {
                            "kind": "stderr",
                            "cell_index": cell_index,
                            "execution_count": self.execution_count,
                            "line": line,
                        }
                    yield {
                        "kind": "cell_error",
                        "cell_index": cell_index,
                        "execution_count": self.execution_count,
                        "line": f"Cell {cell_index + 1} failed",
                    }
                    break
                else:
                    stdout_value = stdout.getvalue().splitlines()
                    stderr_value = stderr.getvalue().splitlines()
                    for line in stdout_value:
                        yield {
                            "kind": "stdout",
                            "cell_index": cell_index,
                            "execution_count": self.execution_count,
                            "line": line,
                        }
                    for line in stderr_value:
                        yield {
                            "kind": "stderr",
                            "cell_index": cell_index,
                            "execution_count": self.execution_count,
                            "line": line,
                        }
                    yield {
                        "kind": "cell_end",
                        "cell_index": cell_index,
                        "execution_count": self.execution_count,
                        "line": f"Finished cell {cell_index + 1}",
                    }


_KERNEL_SESSIONS: dict[str, NotebookKernelSession] = {}
_KERNEL_SESSIONS_LOCK = threading.Lock()


def get_notebook_kernel(kernel_id: str) -> NotebookKernelSession:
    with _KERNEL_SESSIONS_LOCK:
        session = _KERNEL_SESSIONS.get(kernel_id)
        if session is None:
            session = NotebookKernelSession(kernel_id=kernel_id)
            _KERNEL_SESSIONS[kernel_id] = session
        return session


async def stream_notebook_execution(kernel_id: str, cells: list[dict[str, Any]]):
    session = get_notebook_kernel(kernel_id)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    done_marker = object()

    def worker() -> None:
        try:
            for event in session.execute(cells):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, done_marker)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = await queue.get()
        if item is done_marker:
            break
        yield item
