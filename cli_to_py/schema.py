"""Data model for parsed CLI schemas.

Mirrors the TypeScript interfaces in cli-to-js/src/parse-help-text.ts.
All types are plain dataclasses — serializable, comparable, hashable-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedFlag:
    long_name: str
    short_name: str | None
    description: str
    takes_value: bool
    value_name: str | None
    default_value: str | None
    is_negated: bool
    is_required: bool
    choices: list[str] | None
    uses_equals: bool
    is_global: bool


@dataclass
class ParsedPositionalArg:
    name: str
    required: bool
    variadic: bool


@dataclass
class ParsedSubcommand:
    name: str
    aliases: list[str]
    description: str
    flags: list[ParsedFlag] | None = None
    positional_args: list[ParsedPositionalArg] | None = None
    subcommands: list["ParsedSubcommand"] | None = None


@dataclass
class ParsedCommand:
    name: str
    description: str
    flags: list[ParsedFlag] = field(default_factory=list)
    positional_args: list[ParsedPositionalArg] = field(default_factory=list)
    subcommands: list[ParsedSubcommand] = field(default_factory=list)


@dataclass
class CliSchema:
    binary_name: str
    command: ParsedCommand


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int

    def ok(self) -> bool:
        return self.exit_code == 0

    def text(self) -> str:
        """Return stdout stripped of surrounding whitespace."""
        return self.stdout.strip()

    def lines(self) -> list[str]:
        """Return stdout split into lines (empty list if blank)."""
        stripped = self.stdout.strip()
        return stripped.split("\n") if stripped else []

    def json(self, **kwargs: object) -> object:
        """Return json.loads(stdout). Kwargs passed through to json.loads."""
        import json as _json
        return _json.loads(self.stdout, **kwargs)
