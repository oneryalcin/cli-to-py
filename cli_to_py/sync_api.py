"""Synchronous CliApi — subprocess.run-based. Same surface, no asyncio.

Inherits plumbing from `_BaseCliApi` so alias resolution, `_config` kwarg
handling, and equals-flag collection stay in sync with the async variant.

Differences from the async CliApi:
- Methods return `CommandResult` directly (no awaitable wrapper).
- `.text()` / `.lines()` / `.json()` live on `CommandResult` itself.
- `spawn` is not provided — use `convert()` + `await api.spawn(...)` for
  streaming. The sync stdlib doesn't have a clean async-iteration
  equivalent; threaded Popen readers would be a future addition.
- `parse_sync` replaces `parse` (the async variant).
"""

from __future__ import annotations

from typing import Any

from ._api_base import _BaseCliApi, _SubcommandProxy
from .command_string import to_command_string
from .parse_subcommands import parse_subcommand_help_sync
from .schema import CommandResult, ParsedCommand, ParsedSubcommand
from .sync_exec import run_command_sync
from .validate import ValidationError, validate_global_options, validate_options


class SyncCliApi(_BaseCliApi):
    """Sync, callable Pythonic wrapper around a CLI binary."""

    def _dispatch(self, subs: list[str], kwargs: dict[str, Any]) -> CommandResult:
        options, global_opts, per_call = self._split_kwargs(kwargs)
        return run_command_sync(
            self.binary_name, subs, options,
            self._merged_config(per_call), self._equals_for_path(subs), global_opts,
            self._equals_flags,
        )

    def __call__(
        self, subcommand: str | None = None, /, **kwargs: Any
    ) -> CommandResult:
        subs = self._resolve_path(subcommand) if subcommand else []
        return self._dispatch(subs, kwargs)

    def __getattr__(self, name: str) -> _SubcommandProxy:
        if name.startswith("_"):
            raise AttributeError(name)
        node = self._find_subcommand(name)
        if node is None:
            raise AttributeError(
                f"{type(self).__name__!s} has no subcommand {name!r}. "
                f"Use api({name!r}, ...) if your CLI exposes it but --help didn't list it."
            )
        return _SubcommandProxy(self, [node.name], node)

    def __dir__(self) -> list[str]:
        base = set(super().__dir__())
        base.update(self._subcommand_names())
        return sorted(base)

    # ------------------------------------------------------------------ helpers

    def validate(
        self, subcommand: str | None = None, /, **options: Any
    ) -> list[ValidationError]:
        # Same reserved-kwarg contract as execution: a shape validate()
        # accepts must be a shape __call__ accepts.
        options, global_opts, _cfg = self._split_kwargs(options)
        global_errors = (
            validate_global_options(self.schema.command, global_opts)
            if global_opts else []
        )
        if subcommand is None:
            return [*global_errors, *validate_options(self.schema.command, options)]
        sub = self._find_path_node(subcommand)
        if sub is None:
            raise ValueError(
                f'Unknown subcommand "{subcommand}". Pass subcommands=True to convert_sync().'
            )
        if sub.flags is None:
            raise ValueError(
                f'Subcommand "{subcommand}" not enriched. Call parse_sync("{subcommand}") first '
                f'or pass subcommands=True to convert_sync().'
            )
        fake_command = ParsedCommand(
            name=sub.name,
            description=sub.description,
            flags=sub.flags,
            positional_args=sub.positional_args or [],
        )
        return [*global_errors, *validate_options(fake_command, options)]

    def command_string(self, subcommand: str | None = None, /, **kwargs: Any) -> str:
        options, global_opts, _per_call = self._split_kwargs(kwargs)
        subs = self._resolve_path(subcommand) if subcommand else []
        return to_command_string(
            self.binary_name, subs, options, self._equals_for_path(subs),
            global_opts, self._equals_flags,
        )

    def parse_sync(
        self, subcommand_name: str | None = None
    ) -> ParsedCommand | None:
        """Lazily enrich one subcommand (or all) by re-running its --help."""
        if subcommand_name is None:
            from .parse_subcommands import enrich_subcommands_sync
            enrich_subcommands_sync(
                self.binary_name, self.schema,
                timeout=self._default_config.resolved_timeout(),
                cwd=self._default_config.cwd,
                env=self._default_config.env,
            )
            return None
        parsed = parse_subcommand_help_sync(
            self.binary_name, subcommand_name,
            timeout=self._default_config.resolved_timeout(),
            cwd=self._default_config.cwd,
            env=self._default_config.env,
        )
        if parsed is not None:
            existing = self._find_subcommand(subcommand_name)
            if existing is not None:
                existing.flags = parsed.flags
                existing.positional_args = parsed.positional_args
            else:
                self.schema.command.subcommands.append(ParsedSubcommand(
                    name=subcommand_name,
                    aliases=[],
                    description=parsed.description,
                    flags=parsed.flags,
                    positional_args=parsed.positional_args,
                ))
        return parsed
