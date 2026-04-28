"""Recursively enrich a CliSchema with per-subcommand flag data.

Walks the subcommand tree depth-first: for each subcommand discovered in
the root --help, re-run `<binary> <sub> --help` (or `-h`) and parse that
output into per-subcommand flags, positional args, and *nested* subs.
Nested subcommands (e.g. `git remote add`, `kubectl get pods`) are then
recursed into with a longer path.

Failures are tolerated per-subcommand — some subcommands don't support
--help or are hidden aliases. The schema just has `flags=None` for those.
"""

from __future__ import annotations

import asyncio

from .best_help import select_help_output
from .constants import HELP_TIMEOUT_S
from .exec import run_for_help
from .parse_help import parse_help_text
from .schema import CliSchema, ParsedCommand, ParsedSubcommand
from .sync_exec import run_for_help_sync

SUBCOMMAND_HELP_FLAGS = ("-h", "--help")


def _has_content(command: ParsedCommand) -> bool:
    return bool(command.flags or command.subcommands or command.positional_args)


async def parse_subcommand_help(
    binary: str,
    subcommand_path: str | list[str],
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> ParsedCommand | None:
    path = subcommand_path if isinstance(subcommand_path, list) else [subcommand_path]
    display = path[-1]
    for help_flag in SUBCOMMAND_HELP_FLAGS:
        try:
            result = await run_for_help(
                binary, [*path, help_flag], timeout=timeout, cwd=cwd, env=env,
            )
        except Exception:
            continue
        help_text = select_help_output(result.stdout, result.stderr)
        if not help_text.strip():
            continue
        schema = parse_help_text(display, help_text)
        if _has_content(schema.command):
            return schema.command
    return None


def parse_subcommand_help_sync(
    binary: str,
    subcommand_path: str | list[str],
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> ParsedCommand | None:
    path = subcommand_path if isinstance(subcommand_path, list) else [subcommand_path]
    display = path[-1]
    for help_flag in SUBCOMMAND_HELP_FLAGS:
        try:
            result = run_for_help_sync(
                binary, [*path, help_flag], timeout=timeout, cwd=cwd, env=env,
            )
        except Exception:
            continue
        help_text = select_help_output(result.stdout, result.stderr)
        if not help_text.strip():
            continue
        schema = parse_help_text(display, help_text)
        if _has_content(schema.command):
            return schema.command
    return None


# ------------------------------------------------------------------ enrichment

# Cap recursive descent so a mis-parsed CLI can't push us into an unbounded
# tree (an improbable but real failure mode for broken help text).
DEFAULT_MAX_DEPTH = 3


async def _enrich_recursive(
    binary: str,
    subs: list[ParsedSubcommand],
    path: list[str],
    *,
    timeout: float,
    cwd: str | None,
    env: dict[str, str] | None,
    depth: int,
    max_depth: int,
) -> None:
    if depth >= max_depth:
        return

    async def enrich_one(sub: ParsedSubcommand) -> None:
        sub_path = [*path, sub.name]
        parsed = await parse_subcommand_help(
            binary, sub_path, timeout=timeout, cwd=cwd, env=env,
        )
        if parsed is None:
            return
        sub.flags = parsed.flags
        sub.positional_args = parsed.positional_args
        if parsed.subcommands:
            sub.subcommands = parsed.subcommands
            await _enrich_recursive(
                binary, sub.subcommands, sub_path,
                timeout=timeout, cwd=cwd, env=env,
                depth=depth + 1, max_depth=max_depth,
            )

    await asyncio.gather(*(enrich_one(s) for s in subs), return_exceptions=True)


def _enrich_recursive_sync(
    binary: str,
    subs: list[ParsedSubcommand],
    path: list[str],
    *,
    timeout: float,
    cwd: str | None,
    env: dict[str, str] | None,
    depth: int,
    max_depth: int,
) -> None:
    if depth >= max_depth:
        return
    for sub in subs:
        sub_path = [*path, sub.name]
        parsed = parse_subcommand_help_sync(
            binary, sub_path, timeout=timeout, cwd=cwd, env=env,
        )
        if parsed is None:
            continue
        sub.flags = parsed.flags
        sub.positional_args = parsed.positional_args
        if parsed.subcommands:
            sub.subcommands = parsed.subcommands
            _enrich_recursive_sync(
                binary, sub.subcommands, sub_path,
                timeout=timeout, cwd=cwd, env=env,
                depth=depth + 1, max_depth=max_depth,
            )


async def enrich_subcommands(
    binary: str,
    schema: CliSchema,
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> None:
    """Fan out to every subcommand (recursively) in parallel. Tolerates failures."""
    await _enrich_recursive(
        binary, schema.command.subcommands, [],
        timeout=timeout, cwd=cwd, env=env,
        depth=0, max_depth=max_depth,
    )


def enrich_subcommands_sync(
    binary: str,
    schema: CliSchema,
    *,
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> None:
    """Sequential sync enrichment — slower, but no asyncio requirement."""
    _enrich_recursive_sync(
        binary, schema.command.subcommands, [],
        timeout=timeout, cwd=cwd, env=env,
        depth=0, max_depth=max_depth,
    )
