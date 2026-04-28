"""Pick the better of stdout / stderr when asking a binary for its help text.

Some tools print --help to stdout (GNU convention), some to stderr.
Score each by counting "usage/options/commands" signal patterns, pick the
winner. If they tie, prefer the longer one. If both are empty, return "".
"""

from __future__ import annotations

import re

HELP_SIGNAL_PATTERNS = [
    re.compile(r"usage:", re.IGNORECASE),
    re.compile(r"options:", re.IGNORECASE),
    re.compile(r"commands:", re.IGNORECASE),
    re.compile(r"^\s+-", re.MULTILINE),
]


def _score(text: str) -> int:
    return sum(1 for pattern in HELP_SIGNAL_PATTERNS if pattern.search(text))


def select_help_output(stdout: str, stderr: str) -> str:
    trimmed_out = stdout.strip()
    trimmed_err = stderr.strip()

    if not trimmed_out and not trimmed_err:
        return ""
    if not trimmed_err:
        return stdout
    if not trimmed_out:
        return stderr

    out_signals = _score(trimmed_out)
    err_signals = _score(trimmed_err)

    if out_signals and not err_signals:
        return stdout
    if err_signals and not out_signals:
        return stderr
    if out_signals and err_signals:
        return stdout if out_signals >= err_signals else stderr

    return stdout if len(trimmed_out) >= len(trimmed_err) else stderr
