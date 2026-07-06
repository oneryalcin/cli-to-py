"""Subprocess execution — async run_command + spawn_command.

Covers:
- run_command: buffered, returns CommandResult
- spawn_command: CommandProcess for async-iteration streaming
- Streaming callbacks (on_stdout / on_stderr) that fire per-line
- stdio="inherit" for interactive CLIs
- Color auto-detect: FORCE_COLOR + CLICOLOR_FORCE when callbacks fire from a tty
- Timeout enforcement that actually works on shell-wrapped grandchildren
  (kills the full process group on POSIX via os.killpg + SIGKILL)
- Cooperative cancellation via asyncio.Event signal
- BinaryNotFoundError: typed FileNotFoundError wrapper
- CommandTimeout carries partial stdout/stderr captured before the kill
- run_for_help: dedicated minimal spawn for --help queries
"""

from __future__ import annotations

import asyncio
import os
import signal as _signal
import sys
from typing import Any, AsyncIterator

from .constants import HELP_TIMEOUT_S
from .env_utils import build_env
from .options_to_args import options_to_args
from .run_config import RunConfig
from .schema import CommandResult


class CommandTimeout(Exception):
    """Raised when a subprocess exceeds its configured timeout.

    Attaches any stdout/stderr captured before the kill via `.partial_stdout`
    / `.partial_stderr` so a caller can still inspect progress.
    """

    def __init__(self, message: str, partial_stdout: str = "", partial_stderr: str = ""):
        super().__init__(message)
        self.partial_stdout = partial_stdout
        self.partial_stderr = partial_stderr


class CommandAborted(Exception):
    """Raised when a subprocess is killed via its RunConfig.signal."""

    def __init__(self, message: str, partial_stdout: str = "", partial_stderr: str = ""):
        super().__init__(message)
        self.partial_stdout = partial_stdout
        self.partial_stderr = partial_stderr


class BinaryNotFoundError(FileNotFoundError):
    """Raised when a subprocess binary is not found on PATH."""

    def __init__(self, binary: str):
        super().__init__(f"Binary not found: {binary!r}")
        self.binary = binary


def _prepare_argv(
    binary: str,
    subcommands: list[str],
    options: dict[str, Any] | None,
    equals_flags: set[str] | None,
    global_options: dict[str, Any] | None = None,
    global_equals_flags: set[str] | None = None,
) -> list[str]:
    # Global options render BEFORE the subcommand: git -C /path log, docker
    # --context x ps. Rendering them after is rejected by many CLIs. They use
    # the root command's equals policy, not the subcommand's — a subcommand may
    # define a same-named flag with a different form.
    if global_equals_flags is None:
        global_equals_flags = equals_flags
    return [
        binary,
        *options_to_args(global_options or {}, global_equals_flags),
        *subcommands,
        *options_to_args(options or {}, equals_flags),
    ]


def _posix_session_kwargs() -> dict[str, Any]:
    """Kwargs to pass to create_subprocess_exec so the child gets its own
    process group on POSIX — lets us kill the whole group on timeout."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill the subprocess and any of its descendants.

    On POSIX we created the child as session leader via `start_new_session`,
    so `os.killpg(pgid, SIGKILL)` terminates the whole tree. On Windows we
    fall back to `proc.kill()`; a full taskkill /T would be nicer but
    requires shelling out.
    """
    if proc.returncode is not None:
        return
    try:
        if os.name == "posix" and proc.pid is not None:
            try:
                os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
                return
            except (ProcessLookupError, PermissionError):
                pass
        proc.kill()
    except ProcessLookupError:
        pass


async def _spawn(
    argv: list[str],
    *,
    stdout: int | None,
    stderr: int | None,
    cwd: str | None,
    env: dict[str, str] | None,
    stdin: int | None = asyncio.subprocess.DEVNULL,
) -> asyncio.subprocess.Process:
    try:
        return await asyncio.create_subprocess_exec(
            *argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=env,
            **_posix_session_kwargs(),
        )
    except FileNotFoundError as err:
        raise BinaryNotFoundError(argv[0]) from err


async def _read_stream_lines(
    stream: asyncio.StreamReader,
    chunks: list[bytes],
    callback: Any,
) -> None:
    """Consume a stream, appending raw bytes to chunks and firing callback
    per decoded line."""
    leftover = ""
    try:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if callback is not None:
                leftover += chunk.decode("utf-8", errors="replace")
                while "\n" in leftover:
                    line, leftover = leftover.split("\n", 1)
                    try:
                        callback(line + "\n")
                    except Exception:
                        pass  # callback errors must not crash the pipeline
    except asyncio.CancelledError:
        pass
    if callback is not None and leftover:
        try:
            callback(leftover)
        except Exception:
            pass


async def _wait_for_signal(
    signal: asyncio.Event | None, proc: asyncio.subprocess.Process
) -> None:
    if signal is None:
        return
    try:
        await signal.wait()
    except asyncio.CancelledError:
        return
    _kill_tree(proc)


def _decode(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace")


async def run_command(
    binary: str,
    subcommands: list[str] | None = None,
    options: dict[str, Any] | None = None,
    config: RunConfig | None = None,
    equals_flags: set[str] | None = None,
    global_options: dict[str, Any] | None = None,
    global_equals_flags: set[str] | None = None,
) -> CommandResult:
    """Run `binary [global options] subcommands [args from options]`.

    Honors RunConfig: timeout, cwd, env, stdio, streaming callbacks, signal.
    Raises CommandTimeout on timeout, CommandAborted on signal abort,
    BinaryNotFoundError on missing binary.
    """
    subs = list(subcommands or [])
    cfg = config or RunConfig()
    argv = _prepare_argv(
        binary, subs, options, equals_flags, global_options, global_equals_flags
    )
    env = build_env(cfg)
    timeout = cfg.resolved_timeout()
    stdio = cfg.resolved_stdio()

    if stdio == "inherit":
        proc = await _spawn(argv, stdout=None, stderr=None, cwd=cfg.cwd, env=env, stdin=None)
        signal_task = asyncio.create_task(_wait_for_signal(cfg.signal, proc))
        try:
            exit_code = await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _kill_tree(proc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            signal_task.cancel()
            await asyncio.gather(signal_task, return_exceptions=True)
            raise CommandTimeout(f"{binary} timed out after {timeout}s") from None
        signal_task.cancel()
        await asyncio.gather(signal_task, return_exceptions=True)
        if cfg.signal is not None and cfg.signal.is_set() and exit_code != 0:
            raise CommandAborted(f"{binary} aborted")
        return CommandResult(stdout="", stderr="", exit_code=exit_code or 0)

    proc = await _spawn(
        argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cfg.cwd,
        env=env,
    )

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []

    stdout_task = asyncio.create_task(
        _read_stream_lines(proc.stdout, stdout_chunks, cfg.on_stdout)  # type: ignore[arg-type]
    )
    stderr_task = asyncio.create_task(
        _read_stream_lines(proc.stderr, stderr_chunks, cfg.on_stderr)  # type: ignore[arg-type]
    )
    signal_task = asyncio.create_task(_wait_for_signal(cfg.signal, proc))

    try:
        exit_code = await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_tree(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        stdout_task.cancel()
        stderr_task.cancel()
        signal_task.cancel()
        await asyncio.gather(
            stdout_task, stderr_task, signal_task, return_exceptions=True
        )
        raise CommandTimeout(
            f"{binary} timed out after {timeout}s",
            partial_stdout=_decode(stdout_chunks),
            partial_stderr=_decode(stderr_chunks),
        ) from None

    # Cancel signal_task IMMEDIATELY after proc.wait() returns to prevent a
    # late-firing signal from setting signal.is_set() during the drain window.
    # Without this, a signal that fires between proc.wait() and the is_set()
    # check would raise CommandAborted for a successfully completed process.
    signal_task.cancel()
    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
    await asyncio.gather(signal_task, return_exceptions=True)

    # Only raise CommandAborted if the signal actually caused the process to
    # be killed (exit code reflects SIGKILL). A signal that fires after normal
    # completion should be ignored.
    if cfg.signal is not None and cfg.signal.is_set() and exit_code != 0:
        raise CommandAborted(
            f"{binary} aborted",
            partial_stdout=_decode(stdout_chunks),
            partial_stderr=_decode(stderr_chunks),
        )

    return CommandResult(
        stdout=_decode(stdout_chunks),
        stderr=_decode(stderr_chunks),
        exit_code=exit_code or 0,
    )


async def run_for_help(
    binary: str,
    help_args: list[str],
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Minimal spawn for --help queries."""
    proc = await _spawn(
        [binary, *help_args],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_tree(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        raise CommandTimeout(f"{binary} --help timed out after {timeout}s") from None

    return CommandResult(
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        exit_code=proc.returncode or 0,
    )


class CommandProcess:
    """Spawned process wrapper with async line-iteration and optional
    timeout / signal enforcement.

    Usage:
        proc = await spawn_command("git", ["log"], {"oneline": True})
        async for line in proc:
            print(line)
        code = await proc.exit_code()
    """

    def __init__(
        self,
        proc: asyncio.subprocess.Process,
        *,
        timeout: float | None = None,
        signal: asyncio.Event | None = None,
    ):
        self._proc = proc
        self._timeout_task: asyncio.Task | None = None
        self._signal_task: asyncio.Task | None = None
        if timeout is not None:
            self._timeout_task = asyncio.create_task(self._enforce_timeout(timeout))
        if signal is not None:
            self._signal_task = asyncio.create_task(_wait_for_signal(signal, proc))

    async def _enforce_timeout(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        _kill_tree(self._proc)

    @property
    def pid(self) -> int | None:
        return self._proc.pid

    @property
    def stdin(self) -> asyncio.StreamWriter | None:
        return self._proc.stdin

    @property
    def stdout(self) -> asyncio.StreamReader | None:
        return self._proc.stdout

    @property
    def stderr(self) -> asyncio.StreamReader | None:
        return self._proc.stderr

    async def exit_code(self) -> int:
        code = await self._proc.wait()
        self._cancel_background()
        return code or 0

    def kill(self) -> None:
        _kill_tree(self._proc)
        self._cancel_background()

    def terminate(self) -> None:
        if self._proc.returncode is None:
            self._proc.terminate()

    def _cancel_background(self) -> None:
        for task in (self._timeout_task, self._signal_task):
            if task is not None and not task.done():
                task.cancel()

    async def __aiter__(self) -> AsyncIterator[str]:
        if self._proc.stdout is None:
            return
        # Drain stderr concurrently so it doesn't fill the OS pipe buffer
        # (~64KB) and block the child, stalling the stdout iteration.
        stderr_drain = asyncio.create_task(self._drain_stderr())
        leftover = ""
        try:
            while True:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break
                leftover += chunk.decode("utf-8", errors="replace")
                while "\n" in leftover:
                    line, leftover = leftover.split("\n", 1)
                    yield line
            if leftover:
                yield leftover
        finally:
            stderr_drain.cancel()
            await asyncio.gather(stderr_drain, return_exceptions=True)
            self._cancel_background()

    async def _drain_stderr(self) -> None:
        """Read and discard stderr to keep the pipe from filling."""
        if self._proc.stderr is None:
            return
        try:
            while await self._proc.stderr.read(4096):
                pass
        except asyncio.CancelledError:
            pass


async def spawn_command(
    binary: str,
    subcommands: list[str] | None = None,
    options: dict[str, Any] | None = None,
    config: RunConfig | None = None,
    equals_flags: set[str] | None = None,
    global_options: dict[str, Any] | None = None,
    global_equals_flags: set[str] | None = None,
) -> CommandProcess:
    """Spawn a long-running process and return a CommandProcess for streaming.

    Honors RunConfig.timeout and RunConfig.signal — the CommandProcess runs
    background tasks that kill the process group if either fires.
    """
    subs = list(subcommands or [])
    cfg = config or RunConfig()
    argv = _prepare_argv(
        binary, subs, options, equals_flags, global_options, global_equals_flags
    )
    env = build_env(cfg)
    proc = await _spawn(
        argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cfg.cwd,
        env=env,
    )
    return CommandProcess(proc, timeout=cfg.timeout, signal=cfg.signal)
