"""Synchronous execution — subprocess.run/Popen-based equivalents.

Mirrors exec.py but uses the plain (non-async) subprocess module. Streaming
callbacks work per-line via Popen + readline loops; stdio=inherit passes
through to the parent; timeouts enforce via subprocess's own timeout
(SIGKILL on POSIX), and the parent process group is killed on timeout so
grandchildren don't linger.
"""

from __future__ import annotations

import os
import signal as _signal
import subprocess
from typing import Any

from .constants import HELP_TIMEOUT_S
from .env_utils import build_env
from .exec import BinaryNotFoundError, CommandTimeout, _prepare_argv
from .run_config import RunConfig
from .schema import CommandResult


def _start_new_session_kwargs() -> dict[str, Any]:
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def _kill_tree(proc: "subprocess.Popen[Any]") -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
                return
            except (ProcessLookupError, PermissionError):
                pass
        proc.kill()
    except ProcessLookupError:
        pass


def run_command_sync(
    binary: str,
    subcommands: list[str] | None = None,
    options: dict[str, Any] | None = None,
    config: RunConfig | None = None,
    equals_flags: set[str] | None = None,
    global_options: dict[str, Any] | None = None,
    global_equals_flags: set[str] | None = None,
) -> CommandResult:
    subs = list(subcommands or [])
    cfg = config or RunConfig()

    # signal is not supported in sync mode — fail fast instead of silently ignoring.
    if cfg.signal is not None:
        raise TypeError(
            "RunConfig.signal is not supported in sync mode. "
            "Use the async run_command() for cooperative cancellation."
        )

    argv = _prepare_argv(
        binary, subs, options, equals_flags, global_options, global_equals_flags
    )
    env = build_env(cfg)
    timeout = cfg.resolved_timeout()
    stdio = cfg.resolved_stdio()

    if stdio == "inherit":
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cfg.cwd,
                env=env,
                **_start_new_session_kwargs(),
            )
        except FileNotFoundError as err:
            raise BinaryNotFoundError(argv[0]) from err
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.wait(timeout=2)
            raise CommandTimeout(f"{binary} timed out after {timeout}s") from None
        return CommandResult(stdout="", stderr="", exit_code=proc.returncode or 0)

    try:
        proc = subprocess.Popen(
            argv,
            cwd=cfg.cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_start_new_session_kwargs(),
        )
    except FileNotFoundError as err:
        raise BinaryNotFoundError(argv[0]) from err

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        partial_out, partial_err = proc.communicate()
        raise CommandTimeout(
            f"{binary} timed out after {timeout}s",
            partial_stdout=partial_out or "",
            partial_stderr=partial_err or "",
        ) from None

    if cfg.on_stdout and stdout:
        for line in stdout.splitlines(keepends=True):
            try:
                cfg.on_stdout(line)
            except Exception:
                pass
    if cfg.on_stderr and stderr:
        for line in stderr.splitlines(keepends=True):
            try:
                cfg.on_stderr(line)
            except Exception:
                pass

    return CommandResult(
        stdout=stdout or "",
        stderr=stderr or "",
        exit_code=proc.returncode or 0,
    )


def run_for_help_sync(
    binary: str,
    help_args: list[str],
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            [binary, *help_args],
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            **_start_new_session_kwargs(),
        )
    except FileNotFoundError as err:
        raise BinaryNotFoundError(binary) from err
    except subprocess.TimeoutExpired:
        raise CommandTimeout(f"{binary} --help timed out after {timeout}s") from None
    return CommandResult(
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        exit_code=completed.returncode or 0,
    )
