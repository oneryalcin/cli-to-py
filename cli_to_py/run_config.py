"""RunConfig dataclass for per-call execution options.

All fields default to None so `merge()` can reliably distinguish "not set"
from "explicitly set to the default value". Defaults are applied at the
execution site, not at construction time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from .constants import COMMAND_TIMEOUT_S

StdioMode = Literal["pipe", "inherit"]
StreamCallback = Callable[[str], Any]


@dataclass
class RunConfig:
    """Per-call execution config. Mirrors cli-to-js RunConfig interface.

    timeout     Seconds before the subprocess is killed. Default 30s
                (applied in run_command when None).
    cwd         Working directory for the subprocess.
    env         Environment override. Merged with parent process env when set;
                also merged across base and per-call configs.
    stdio       "pipe" (default) or "inherit" to pass through to the parent tty.
    on_stdout   Callback invoked per-line as stdout arrives.
                Async: real-time per-chunk. Sync: per-line after completion.
    on_stderr   Same as on_stdout but for stderr.
    signal      asyncio.Event-compatible object. When set, the subprocess
                is killed. (Python equivalent of JS AbortSignal.)
    """

    timeout: float | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None
    stdio: StdioMode | None = None
    on_stdout: StreamCallback | None = None
    on_stderr: StreamCallback | None = None
    signal: Any = None

    def merge(self, other: "RunConfig | None") -> "RunConfig":
        """Return a new config with `other`'s non-None fields overriding `self`.

        `env` is the only field that *combines* (dict-merge); every other
        field follows "explicit overlay wins, None means unset".
        """
        if other is None:
            return self
        merged_env: dict[str, str] | None = None
        if self.env is not None or other.env is not None:
            merged_env = {}
            if self.env:
                merged_env.update(self.env)
            if other.env:
                merged_env.update(other.env)
        return RunConfig(
            timeout=other.timeout if other.timeout is not None else self.timeout,
            cwd=other.cwd if other.cwd is not None else self.cwd,
            env=merged_env,
            stdio=other.stdio if other.stdio is not None else self.stdio,
            on_stdout=other.on_stdout if other.on_stdout is not None else self.on_stdout,
            on_stderr=other.on_stderr if other.on_stderr is not None else self.on_stderr,
            signal=other.signal if other.signal is not None else self.signal,
        )

    def resolved_timeout(self) -> float:
        """Return the timeout, falling back to the module default when unset."""
        return self.timeout if self.timeout is not None else COMMAND_TIMEOUT_S

    def resolved_stdio(self) -> StdioMode:
        return self.stdio if self.stdio is not None else "pipe"
