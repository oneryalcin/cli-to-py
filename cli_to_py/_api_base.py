"""Shared plumbing for CliApi (async) and SyncCliApi (sync).

These helpers were duplicated across api.py and sync_api.py byte-for-byte.
Extracted here so a change to alias resolution or kwargs handling lands
in exactly one place.
"""

from __future__ import annotations

from typing import Any

from .case import kebab_to_snake, snake_to_kebab
from .run_config import RunConfig
from .schema import CliSchema, ParsedSubcommand


class _BaseCliApi:
    """Base class holding dispatch/resolution plumbing shared by CliApi and SyncCliApi.

    Subclasses own `__call__` and `__getattr__` semantics (async vs sync) but
    share alias resolution, equals-flag collection, config merging, and the
    `_config` kwarg extraction convention.
    """

    binary_name: str
    schema: CliSchema
    _default_config: RunConfig
    _equals_flags: set[str]

    def __init__(
        self,
        binary_name: str,
        schema: CliSchema,
        default_config: RunConfig | None = None,
    ):
        self.binary_name = binary_name
        self.schema = schema
        self._default_config = default_config or RunConfig()
        self._equals_flags = {
            kebab_to_snake(f.long_name) for f in schema.command.flags if f.uses_equals
        }

    # --- resolution helpers

    def _resolve_alias(self, name: str) -> str:
        normalized = snake_to_kebab(name)
        for sub in self.schema.command.subcommands:
            if (
                sub.name == name
                or sub.name == normalized
                or (sub.aliases and (name in sub.aliases or normalized in sub.aliases))
            ):
                return sub.name
        return name

    def _find_subcommand(self, name: str) -> ParsedSubcommand | None:
        normalized = snake_to_kebab(name)
        for sub in self.schema.command.subcommands:
            if (
                sub.name == name
                or sub.name == normalized
                or (sub.aliases and (name in sub.aliases or normalized in sub.aliases))
            ):
                return sub
        return None

    def _equals_for(self, resolved_sub: str) -> set[str]:
        sub = self._find_subcommand(resolved_sub)
        if sub is None or not sub.flags:
            return self._equals_flags
        sub_equals = {kebab_to_snake(f.long_name) for f in sub.flags if f.uses_equals}
        return self._equals_flags | sub_equals

    def _split_kwargs(
        self, kwargs: dict[str, Any]
    ) -> tuple[dict[str, Any], RunConfig | None]:
        """Extract an optional `_config` kwarg (a RunConfig) from user options.

        Also guards against the common typo where a user passes
        `config=RunConfig(...)` instead of `_config=RunConfig(...)` — without
        the underscore it would serialize to argv as `--config <repr>`, which
        is never what the user intended.
        """
        config = kwargs.pop("_config", None)
        if config is not None and not isinstance(config, RunConfig):
            raise TypeError("_config must be a RunConfig instance")
        # Stray RunConfig values under non-underscore keys are almost always typos.
        for key, value in kwargs.items():
            if isinstance(value, RunConfig):
                raise TypeError(
                    f"kwarg {key!r} holds a RunConfig — did you mean `_config=...`?"
                )
        return kwargs, config

    def _merged_config(self, per_call: RunConfig | None) -> RunConfig:
        return self._default_config.merge(per_call)

    # --- introspection helpers

    def _subcommand_names(self) -> list[str]:
        """Return known subcommand names and aliases, without duplicates."""
        names: list[str] = []
        seen: set[str] = set()
        for sub in self.schema.command.subcommands:
            if sub.name not in seen:
                names.append(sub.name)
                seen.add(sub.name)
            for alias in sub.aliases or ():
                if alias not in seen:
                    names.append(alias)
                    seen.add(alias)
        return names
