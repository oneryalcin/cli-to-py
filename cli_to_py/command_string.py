"""Serialize a command to a shell-safe string (for $command mode / script chaining)."""

from __future__ import annotations

import shlex
from typing import Any

from .options_to_args import options_to_args


def to_command_string(
    binary: str,
    subcommands: list[str] | None = None,
    options: dict[str, Any] | None = None,
    equals_flags: set[str] | None = None,
    global_options: dict[str, Any] | None = None,
) -> str:
    subs = list(subcommands or [])
    parts = [
        binary,
        *options_to_args(global_options or {}, equals_flags),
        *subs,
        *options_to_args(options or {}, equals_flags),
    ]
    return " ".join(shlex.quote(part) for part in parts)
