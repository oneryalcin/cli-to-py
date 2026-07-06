"""cli_to_py — Turn any CLI into a Python API, automatically.

Public API:

    from cli_to_py import convert, convert_sync, from_help_text

    # Async
    git = await convert("git")
    result = await git.status(short=True)
    branch = await git.branch(show_current=True).text()
    errors = git.validate("commit", massage="x")    # returns [ValidationError]

    # Sync
    git = convert_sync("git")
    result = git.status(short=True)

    # Static help text
    api = from_help_text("my-tool", help_text)
"""

from __future__ import annotations

from .api import CliApi
from .cache import cache_dir, clear_cache, load_cached_schema, save_cached_schema
from .command_future import CommandFuture
from .command_string import to_command_string
from .convert import convert, convert_sync, from_help_text, from_help_text_sync
from .exec import (
    BinaryNotFoundError,
    CommandAborted,
    CommandProcess,
    CommandTimeout,
    run_command,
    run_for_help,
    spawn_command,
)
from .generate import generate_json, generate_stub, generate_wrapper
from .load_schema import load_schema, load_schema_sync
from .options_to_args import options_to_args
from .parse_help import parse_help_text, strip_ansi
from .parse_subcommands import enrich_subcommands, parse_subcommand_help
from .run_config import RunConfig
from .schema import (
    CliSchema,
    CommandResult,
    ParsedCommand,
    ParsedFlag,
    ParsedPositionalArg,
    ParsedSubcommand,
)
from .script import Script, script
from .sync_api import SyncCliApi
from .sync_exec import run_command_sync, run_for_help_sync
from .validate import ValidationError, validate_global_options, validate_options

__version__ = "0.1.0"

__all__ = [
    # version
    "__version__",
    # entry points
    "convert",
    "convert_sync",
    "from_help_text",
    "from_help_text_sync",
    "load_schema",
    "load_schema_sync",
    # api objects
    "CliApi",
    "SyncCliApi",
    "CommandFuture",
    "CommandProcess",
    # schema types
    "CliSchema",
    "ParsedCommand",
    "ParsedSubcommand",
    "ParsedFlag",
    "ParsedPositionalArg",
    "CommandResult",
    # config
    "RunConfig",
    # validation
    "validate_global_options",
    "validate_options",
    "ValidationError",
    # execution
    "run_command",
    "run_command_sync",
    "run_for_help",
    "run_for_help_sync",
    "spawn_command",
    "CommandTimeout",
    "CommandAborted",
    "BinaryNotFoundError",
    # parsing
    "parse_help_text",
    "strip_ansi",
    "parse_subcommand_help",
    "enrich_subcommands",
    "options_to_args",
    "to_command_string",
    # codegen
    "generate_wrapper",
    "generate_stub",
    "generate_json",
    # script chaining
    "Script",
    "script",
    # cache
    "cache_dir",
    "load_cached_schema",
    "save_cached_schema",
    "clear_cache",
]
