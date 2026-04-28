"""Orchestrator: spawn --help, parse, optionally enrich subcommands."""

from __future__ import annotations

from .best_help import select_help_output
from .constants import HELP_TIMEOUT_S
from .exec import run_for_help
from .parse_help import parse_help_text
from .parse_subcommands import enrich_subcommands, enrich_subcommands_sync
from .schema import CliSchema
from .sync_exec import run_for_help_sync


async def load_schema(
    binary_name: str,
    *,
    help_flag: str = "--help",
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    subcommands: bool = True,
) -> CliSchema:
    result = await run_for_help(binary_name, [help_flag], timeout=timeout, cwd=cwd, env=env)
    help_text = select_help_output(result.stdout, result.stderr)
    schema = parse_help_text(binary_name, help_text)
    if subcommands and schema.command.subcommands:
        await enrich_subcommands(binary_name, schema, timeout=timeout, cwd=cwd, env=env)
    return schema


def load_schema_sync(
    binary_name: str,
    *,
    help_flag: str = "--help",
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    subcommands: bool = True,
) -> CliSchema:
    result = run_for_help_sync(binary_name, [help_flag], timeout=timeout, cwd=cwd, env=env)
    help_text = select_help_output(result.stdout, result.stderr)
    schema = parse_help_text(binary_name, help_text)
    if subcommands and schema.command.subcommands:
        enrich_subcommands_sync(binary_name, schema, timeout=timeout, cwd=cwd, env=env)
    return schema
