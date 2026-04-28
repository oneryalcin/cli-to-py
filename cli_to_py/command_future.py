"""Awaitable wrapper around a CommandResult with .text() / .lines() / .json() conveniences.

Eager-task pattern: the underlying coroutine is wrapped in an asyncio.Task
immediately in __init__ if a running loop is available. This means
`api.status()` (without `await`) still schedules the subprocess and won't
emit Python's "coroutine was never awaited" RuntimeWarning.

Users can then either `await fut` (returns CommandResult) or
`await fut.text()` / `.lines()` / `.json()` on the same future. The task
is memoized, so all three methods plus `__await__` share one execution.
"""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any, Awaitable, Generator

from .schema import CommandResult


class CommandFuture:
    def __init__(self, coro: Awaitable[CommandResult]):
        self._coro = coro
        self._task: asyncio.Task[CommandResult] | None = None
        # Schedule eagerly if a loop is running so the coroutine is owned
        # by the event loop and won't trigger "never awaited" warnings.
        try:
            asyncio.get_running_loop()
            self._task = asyncio.ensure_future(coro)  # type: ignore[arg-type]
        except RuntimeError:
            pass

    def _as_task(self) -> asyncio.Task[CommandResult]:
        if self._task is None:
            self._task = asyncio.ensure_future(self._coro)  # type: ignore[arg-type]
        return self._task

    def __await__(self) -> Generator[Any, None, CommandResult]:
        return self._as_task().__await__()

    async def text(self) -> str:
        """Return stdout stripped of surrounding whitespace."""
        result = await self._as_task()
        return result.text()

    async def lines(self) -> list[str]:
        """Return stdout split into lines (empty list if blank)."""
        result = await self._as_task()
        return result.lines()

    async def json(self, **kwargs: Any) -> Any:
        """Return json.loads(stdout). Kwargs passed through to json.loads."""
        result = await self._as_task()
        return _json.loads(result.stdout, **kwargs)
