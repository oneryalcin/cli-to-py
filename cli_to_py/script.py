"""Compose multiple commands into a runnable shell script.

Chains commands with && so execution stops on the first failure. Usable
both as an async runner and as a plain shell string (via `str(script)`).

Uses start_new_session + process-group kill so grandchildren spawned by
shell-chained commands are properly terminated on timeout.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from .exec import _kill_tree, _posix_session_kwargs
from .schema import CommandResult
from .sync_exec import _kill_tree as _kill_tree_sync
from .sync_exec import _start_new_session_kwargs


class Script:
    """A chain of shell command strings joined with `&&`.

    Usage:
        s = Script("git commit -m x", "git push")
        await s.run()           # async, uses /bin/sh -c
        s.run_sync()            # sync
        str(s)                  # "git commit -m x && git push"
    """

    def __init__(self, *steps: str):
        self.steps: list[str] = [s for s in steps if s]

    def __str__(self) -> str:
        return " && ".join(self.steps)

    def __repr__(self) -> str:
        return f"Script({self.steps!r})"

    def __add__(self, other: "Script | str") -> "Script":
        if isinstance(other, Script):
            return Script(*self.steps, *other.steps)
        return Script(*self.steps, other)

    async def run(
        self,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Run the chain asynchronously. Uses sh -c so && is interpreted."""
        if not self.steps:
            return CommandResult(stdout="", stderr="", exit_code=0)
        proc = await asyncio.create_subprocess_exec(
            "sh", "-c", str(self),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            **_posix_session_kwargs(),
        )
        try:
            if timeout is not None:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            else:
                stdout, stderr = await proc.communicate()
        except asyncio.TimeoutError:
            _kill_tree(proc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            raise
        return CommandResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else 1,
        )

    def run_sync(
        self,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        if not self.steps:
            return CommandResult(stdout="", stderr="", exit_code=0)
        proc = subprocess.Popen(
            ["sh", "-c", str(self)],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_start_new_session_kwargs(),
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree_sync(proc)
            proc.wait(timeout=2)
            raise
        return CommandResult(
            stdout=(stdout or b"").decode("utf-8", errors="replace"),
            stderr=(stderr or b"").decode("utf-8", errors="replace"),
            exit_code=proc.returncode,
        )


def script(*steps: str) -> Script:
    """Build a Script from one or more command strings."""
    return Script(*steps)
