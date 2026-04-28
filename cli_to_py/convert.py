"""Top-level entry points: convert(), convert_sync(), from_help_text()."""

from __future__ import annotations

from .api import CliApi
from .cache import load_cached_schema, save_cached_schema
from .constants import HELP_TIMEOUT_S
from .load_schema import load_schema, load_schema_sync
from .parse_help import parse_help_text
from .run_config import RunConfig
from .sync_api import SyncCliApi


async def convert(
    binary_name: str,
    *,
    help_flag: str = "--help",
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    subcommands: bool = True,
    use_cache: bool = False,
    default_config: RunConfig | None = None,
) -> CliApi:
    """Async: spawn `binary --help`, parse, optionally enrich, return CliApi.

    Args:
        binary_name: name or absolute path of the CLI binary.
        help_flag: flag to request help. Default "--help".
        timeout: per-spawn timeout (seconds).
        cwd: working dir override for help queries (not commands).
        env: env override for help queries.
        subcommands: if True (default), recursively enrich each subcommand.
        use_cache: if True, persist parsed schema to ~/.cache/cli-to-py/ and
                   read it back on subsequent calls (keyed by binary path+mtime).
        default_config: RunConfig defaults applied to every subsequent call.
    """
    schema = None
    if use_cache:
        schema = load_cached_schema(binary_name, subcommands=subcommands)
    if schema is None:
        schema = await load_schema(
            binary_name,
            help_flag=help_flag,
            timeout=timeout,
            cwd=cwd,
            env=env,
            subcommands=subcommands,
        )
        if use_cache:
            save_cached_schema(schema, subcommands=subcommands)
    return CliApi(binary_name, schema, default_config=default_config)


def convert_sync(
    binary_name: str,
    *,
    help_flag: str = "--help",
    timeout: float = HELP_TIMEOUT_S,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    subcommands: bool = True,
    use_cache: bool = False,
    default_config: RunConfig | None = None,
) -> SyncCliApi:
    """Sync equivalent of convert(). Uses subprocess.run, no asyncio required."""
    schema = None
    if use_cache:
        schema = load_cached_schema(binary_name, subcommands=subcommands)
    if schema is None:
        schema = load_schema_sync(
            binary_name,
            help_flag=help_flag,
            timeout=timeout,
            cwd=cwd,
            env=env,
            subcommands=subcommands,
        )
        if use_cache:
            save_cached_schema(schema, subcommands=subcommands)
    return SyncCliApi(binary_name, schema, default_config=default_config)


def from_help_text(
    binary_name: str,
    help_text: str,
    *,
    default_config: RunConfig | None = None,
) -> CliApi:
    """Build a CliApi from static help text (skip spawning)."""
    schema = parse_help_text(binary_name, help_text)
    return CliApi(binary_name, schema, default_config=default_config)


def from_help_text_sync(
    binary_name: str,
    help_text: str,
    *,
    default_config: RunConfig | None = None,
) -> SyncCliApi:
    schema = parse_help_text(binary_name, help_text)
    return SyncCliApi(binary_name, schema, default_config=default_config)
