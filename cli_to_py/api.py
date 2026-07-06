"""Public CliApi class — async Pythonic wrapper around a CLI binary.

Pythonic design: `__getattr__` + `__call__` replace JS's Proxy. Ordinary
attributes (binary_name, schema, helper methods) are resolved normally;
only attribute names that match a parsed subcommand get routed through
`__getattr__` to a dynamic dispatcher. Unknown attribute names raise
AttributeError (so `hasattr(api, 'nonexistent')` is False and IDE
introspection works).

Usage:
    api = await convert("git")
    await api.status(short=True)
    await api("diff", name_only=True, _=["HEAD~1"])
    await api.branch(show_current=True).text()

    api.schema                                       # parsed schema
    api.validate("commit", massage="x")              # typo catcher
    api.command_string("commit", message="x")        # shell string
    proc = await api.spawn("log", oneline=True)      # streaming
    async for line in proc: ...

Reserved method names (can't reach a same-named subcommand via dot
notation): `validate`, `command_string`, `spawn`, `parse`, `schema`,
`binary_name`. If your CLI has a subcommand named (e.g.) `validate`,
use `api("validate", ...)` or `api.__call__("validate", ...)` instead.
"""

from __future__ import annotations

from typing import Any

from ._api_base import _BaseCliApi
from .command_future import CommandFuture
from .command_string import to_command_string
from .exec import CommandProcess, run_command, spawn_command
from .parse_subcommands import parse_subcommand_help
from .schema import ParsedCommand, ParsedSubcommand
from .validate import ValidationError, validate_global_options, validate_options


class CliApi(_BaseCliApi):
    """Async, callable Pythonic wrapper around a CLI binary."""

    def __call__(self, subcommand: str | None = None, /, **kwargs: Any) -> CommandFuture:
        options, global_opts, per_call = self._split_kwargs(kwargs)
        if subcommand is not None:
            resolved = self._resolve_alias(subcommand)
            equals = self._equals_for(resolved)
            return CommandFuture(run_command(
                self.binary_name, [resolved], options,
                self._merged_config(per_call), equals, global_opts,
            ))
        return CommandFuture(run_command(
            self.binary_name, [], options,
            self._merged_config(per_call), self._equals_flags, global_opts,
        ))

    def __getattr__(self, name: str) -> Any:
        # Only called if normal attribute lookup fails — so class methods
        # like `validate`, `spawn`, `command_string`, `parse` still win.
        if name.startswith("_"):
            raise AttributeError(name)
        if self._find_subcommand(name) is None:
            raise AttributeError(
                f"{type(self).__name__!s} has no subcommand {name!r}. "
                f"Use api({name!r}, ...) if your CLI exposes it but --help didn't list it."
            )
        resolved = self._resolve_alias(name)
        equals = self._equals_for(resolved)

        def dispatch(**kwargs: Any) -> CommandFuture:
            options, global_opts, per_call = self._split_kwargs(kwargs)
            return CommandFuture(run_command(
                self.binary_name, [resolved], options,
                self._merged_config(per_call), equals, global_opts,
            ))
        dispatch.__name__ = name
        return dispatch

    def __dir__(self) -> list[str]:
        """Expose known subcommands + helper methods for IDEs / dir()."""
        base = set(super().__dir__())
        base.update(self._subcommand_names())
        return sorted(base)

    # ------------------------------------------------------------------ helpers

    def validate(
        self, subcommand: str | None = None, /, **options: Any
    ) -> list[ValidationError]:
        global_opts = options.pop("_global", None)
        global_errors = (
            validate_global_options(self.schema.command, global_opts)
            if isinstance(global_opts, dict) else []
        )
        if subcommand is None:
            return [*global_errors, *validate_options(self.schema.command, options)]
        sub = self._find_subcommand(subcommand)
        if sub is None:
            raise ValueError(
                f'Unknown subcommand "{subcommand}". Pass subcommands=True to convert().'
            )
        if sub.flags is None:
            raise ValueError(
                f'Subcommand "{subcommand}" not enriched. Call parse("{subcommand}") first '
                f'or pass subcommands=True to convert().'
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
        if subcommand is None:
            return to_command_string(
                self.binary_name, [], options, self._equals_flags, global_opts
            )
        resolved = self._resolve_alias(subcommand)
        return to_command_string(
            self.binary_name, [resolved], options, self._equals_for(resolved), global_opts
        )

    async def spawn(
        self, subcommand: str | None = None, /, **kwargs: Any
    ) -> CommandProcess:
        options, global_opts, per_call = self._split_kwargs(kwargs)
        subs = [self._resolve_alias(subcommand)] if subcommand else []
        equals = self._equals_for(subs[0]) if subs else self._equals_flags
        return await spawn_command(
            self.binary_name, subs, options,
            self._merged_config(per_call), equals, global_opts,
        )

    async def parse(self, subcommand_name: str | None = None) -> ParsedCommand | None:
        """Lazily enrich one subcommand (or all) by re-running its --help."""
        if subcommand_name is None:
            from .parse_subcommands import enrich_subcommands
            await enrich_subcommands(
                self.binary_name, self.schema,
                timeout=self._default_config.resolved_timeout(),
                cwd=self._default_config.cwd,
                env=self._default_config.env,
            )
            return None
        parsed = await parse_subcommand_help(
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
