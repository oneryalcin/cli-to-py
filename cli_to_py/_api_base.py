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


def _match_subcommand(
    subs: list[ParsedSubcommand] | None, name: str
) -> ParsedSubcommand | None:
    """Find a subcommand in `subs` by name, kebab-cased name, or alias."""
    normalized = snake_to_kebab(name)
    for sub in subs or []:
        if (
            sub.name == name
            or sub.name == normalized
            or (sub.aliases and (name in sub.aliases or normalized in sub.aliases))
        ):
            return sub
    return None


class _SubcommandProxy:
    """Callable handle for a subcommand path — `api.pip` / `api.pip.install`.

    Calling it dispatches the accumulated path; attribute access descends
    into nested subcommands parsed from `--help` enrichment.
    """

    def __init__(self, api: "_BaseCliApi", path: list[str], node: ParsedSubcommand):
        self._api = api
        self._path = path
        self._node = node

    def __call__(self, **kwargs: Any) -> Any:
        return self._api._dispatch(self._path, kwargs)

    def __getattr__(self, name: str) -> "_SubcommandProxy":
        if name.startswith("_"):
            raise AttributeError(name)
        child = _match_subcommand(self._node.subcommands, name)
        if child is None:
            joined = " ".join(self._path)
            raise AttributeError(
                f"{joined!r} has no nested subcommand {name!r}. "
                f"Use api({joined + ' ' + name!r}, ...) if your CLI exposes it "
                f"but --help didn't list it."
            )
        return _SubcommandProxy(self._api, [*self._path, child.name], child)

    def __dir__(self) -> list[str]:
        names = set(super().__dir__())
        for sub in self._node.subcommands or []:
            names.add(sub.name)
            names.update(sub.aliases or ())
        return sorted(names)

    @property
    def __name__(self) -> str:
        return self._path[-1]

    def __repr__(self) -> str:
        return f"<{self._api.binary_name} {' '.join(self._path)} dispatcher>"


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

    def _dispatch(self, subs: list[str], kwargs: dict[str, Any]) -> Any:
        raise NotImplementedError  # CliApi / SyncCliApi own the run semantics

    def _resolve_alias(self, name: str) -> str:
        sub = self._find_subcommand(name)
        return sub.name if sub is not None else name

    def _find_subcommand(self, name: str) -> ParsedSubcommand | None:
        return _match_subcommand(self.schema.command.subcommands, name)

    def _resolve_path(self, spec: str) -> list[str]:
        """Resolve a space-separated subcommand spec ('pip install') level by
        level. Segments the schema doesn't know pass through unchanged so
        undocumented subcommands stay dispatchable."""
        resolved: list[str] = []
        subs = self.schema.command.subcommands
        for part in spec.split():
            node = _match_subcommand(subs, part)
            if node is None:
                resolved.append(part)
                subs = None
            else:
                resolved.append(node.name)
                subs = node.subcommands
        return resolved

    def _find_path_node(self, spec: str) -> ParsedSubcommand | None:
        node: ParsedSubcommand | None = None
        subs = self.schema.command.subcommands
        for part in spec.split():
            node = _match_subcommand(subs, part)
            if node is None:
                return None
            subs = node.subcommands
        return node

    def _equals_for_path(self, path: list[str]) -> set[str]:
        equals = set(self._equals_flags)
        subs = self.schema.command.subcommands
        for part in path:
            node = _match_subcommand(subs, part)
            if node is None:
                break
            if node.flags:
                equals |= {kebab_to_snake(f.long_name) for f in node.flags if f.uses_equals}
            subs = node.subcommands
        return equals

    def _equals_for(self, resolved_sub: str) -> set[str]:
        return self._equals_for_path([resolved_sub])

    def _attach_parsed(self, path: list[str], parsed: Any) -> None:
        """Write lazily parsed help data back into the schema at `path`.

        Missing segments are created along the way (flags=None, i.e.
        unenriched) so `parse("remote add")` works even when the root help
        never mentioned `remote` — the subcommands=False recovery path.
        """
        siblings = self.schema.command.subcommands
        for part in path[:-1]:
            node = _match_subcommand(siblings, part)
            if node is None:
                node = ParsedSubcommand(name=part, aliases=[], description="")
                siblings.append(node)
            if node.subcommands is None:
                node.subcommands = []
            siblings = node.subcommands
        leaf = _match_subcommand(siblings, path[-1])
        if leaf is None:
            leaf = ParsedSubcommand(
                name=path[-1], aliases=[], description=parsed.description,
            )
            siblings.append(leaf)
        leaf.flags = parsed.flags
        leaf.positional_args = parsed.positional_args
        if parsed.subcommands:
            leaf.subcommands = parsed.subcommands

    def _unknown_path_message(self, spec: str, convert_call: str, parse_call: str) -> str:
        """Accurate error for a spec _find_path_node couldn't resolve: says
        which segment is unknown and that the call form can still dispatch it."""
        known: list[str] = []
        subs = self.schema.command.subcommands
        for part in spec.split():
            node = _match_subcommand(subs, part)
            if node is None:
                if known:
                    return (
                        f'"{part}" is not a parsed subcommand of "{" ".join(known)}". '
                        f"api({spec!r}, ...) can still dispatch it; validation only "
                        f"covers subcommands found in --help. "
                        f'Call {parse_call}("{spec}") to enrich it.'
                    )
                break
            known.append(node.name)
            subs = node.subcommands
        return f'Unknown subcommand "{spec}". Pass subcommands=True to {convert_call}.'

    def _split_kwargs(
        self, kwargs: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any] | None, RunConfig | None]:
        """Extract the reserved `_config` and `_global` kwargs from user options.

        `_global` is a dict of options rendered BEFORE the subcommand
        (`git -C /path log`, `docker --context x ps`) — many CLIs reject
        global flags placed after the subcommand.

        Also guards against the common typo where a user passes
        `config=RunConfig(...)` instead of `_config=RunConfig(...)` — without
        the underscore it would serialize to argv as `--config <repr>`, which
        is never what the user intended.
        """
        config = kwargs.pop("_config", None)
        if config is not None and not isinstance(config, RunConfig):
            raise TypeError("_config must be a RunConfig instance")
        global_options = kwargs.pop("_global", None)
        if global_options is not None:
            if not isinstance(global_options, dict):
                raise TypeError("_global must be a dict of pre-subcommand options")
            if "_" in global_options:
                raise TypeError(
                    "_global cannot contain '_' — positionals belong after the subcommand"
                )
        # Stray RunConfig values under non-underscore keys are almost always typos.
        for key, value in kwargs.items():
            if isinstance(value, RunConfig):
                raise TypeError(
                    f"kwarg {key!r} holds a RunConfig — did you mean `_config=...`?"
                )
        return kwargs, global_options, config

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
