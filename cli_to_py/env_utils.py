"""Shared environment / color-detection helpers for exec.py and sync_exec.py.

Extracted to avoid drift between the async and sync paths — both need
identical semantics for FORCE_COLOR / CLICOLOR_FORCE / env merging.
"""

from __future__ import annotations

import os
import sys

from .run_config import RunConfig


def should_force_color(config: RunConfig) -> bool:
    """Force color when we're streaming into a tty via callbacks.

    Mirrors cli-to-js shouldForceColor. Checks stdout OR stderr tty depending
    on which callback is registered.
    """
    if not (config.on_stdout or config.on_stderr):
        return False
    if config.on_stdout and sys.stdout.isatty():
        return True
    if config.on_stderr and sys.stderr.isatty():
        return True
    return False


def build_env(config: RunConfig) -> dict[str, str] | None:
    """Build the subprocess env dict.

    Returns None if no override is needed (subprocess inherits the parent env).
    Otherwise returns a merged dict: parent env + config.env + color forcing.
    """
    force_color = should_force_color(config)
    if config.env is None and not force_color:
        return None
    base = dict(os.environ)
    if config.env:
        base.update(config.env)
    if force_color:
        base["FORCE_COLOR"] = "1"
        base["CLICOLOR_FORCE"] = "1"
        base.pop("NO_COLOR", None)
    return base
