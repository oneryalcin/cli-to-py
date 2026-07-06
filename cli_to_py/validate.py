"""Validate kwargs against a ParsedCommand schema — the error-correction loop.

Returns a list of structured ValidationError objects (empty = valid). The
agent-safety pattern: call this BEFORE spawning, catch typos, use the
.suggestion field to self-correct in one retry.

Error kinds:
- unknown-flag         : key not in schema; carries a did-you-mean suggestion
- type-mismatch        : value type doesn't match flag's takes_value
- invalid-choice       : value not in flag.choices
- missing-required-flag: schema.is_required but key missing from options
- missing-positional   : fewer `_` entries than required positionals
- variadic-mismatch    : too many positionals for non-variadic command
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from .case import kebab_to_snake
from .constants import MAX_SUGGESTION_CUTOFF
from .schema import ParsedCommand, ParsedFlag


@dataclass
class ValidationError:
    kind: str
    name: str
    message: str
    suggestion: str | None = None
    choices: list[str] | None = None


def _build_flag_lookup(flags: list[ParsedFlag]) -> dict[str, ParsedFlag]:
    lookup: dict[str, ParsedFlag] = {}
    for flag in flags:
        lookup[kebab_to_snake(flag.long_name)] = flag
        lookup[f"--{flag.long_name}"] = flag
        if flag.short_name:
            lookup[flag.short_name.lstrip("-")] = flag
            lookup[flag.short_name] = flag
    return lookup


def _option_keys_for_flag(flag: ParsedFlag) -> set[str]:
    keys = {kebab_to_snake(flag.long_name), f"--{flag.long_name}"}
    if flag.short_name:
        keys.add(flag.short_name.lstrip("-"))
        keys.add(flag.short_name)
    return keys


def _validate_flags(
    options: dict[str, Any],
    lookup: dict[str, ParsedFlag],
    check_required: bool = True,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    known = list(lookup.keys())

    for key, value in options.items():
        if key == "_" or key.startswith("-"):
            continue
        flag = lookup.get(key)
        if flag is None:
            matches = difflib.get_close_matches(key, known, n=1, cutoff=MAX_SUGGESTION_CUTOFF)
            suggestion = matches[0] if matches else None
            hint = f' Did you mean "{suggestion}"?' if suggestion else ""
            errors.append(ValidationError(
                kind="unknown-flag",
                name=key,
                message=f'Unknown flag "{key}".{hint}',
                suggestion=suggestion,
            ))
            continue
        if flag.takes_value and isinstance(value, bool):
            errors.append(ValidationError(
                kind="type-mismatch",
                name=key,
                message=f'Flag "{key}" expects a value but received a boolean.',
            ))
        elif not flag.takes_value and isinstance(value, str):
            errors.append(ValidationError(
                kind="type-mismatch",
                name=key,
                message=f'Flag "{key}" is a boolean flag but received a string value.',
            ))
        if flag.choices:
            values: list[Any] = (
                list(value) if isinstance(value, (list, tuple))
                else [value] if isinstance(value, str)
                else []
            )
            for single in values:
                if str(single) not in flag.choices:
                    errors.append(ValidationError(
                        kind="invalid-choice",
                        name=key,
                        message=f'Flag "{key}" received "{single}" but must be one of: {", ".join(flag.choices)}.',
                        choices=list(flag.choices),
                    ))

    if not check_required:
        return errors

    checked_required: set[int] = set()
    for snake_name, flag in lookup.items():
        flag_id = id(flag)
        if flag_id in checked_required:
            continue
        checked_required.add(flag_id)
        if flag.is_required and not (_option_keys_for_flag(flag) & options.keys()):
            errors.append(ValidationError(
                kind="missing-required-flag",
                name=kebab_to_snake(flag.long_name),
                message=f'Required flag "{snake_name}" (--{flag.long_name}) is missing.',
            ))
    return errors


def _validate_positionals(options: dict[str, Any], command: ParsedCommand) -> list[ValidationError]:
    errors: list[ValidationError] = []
    raw = options.get("_", [])
    provided = raw if isinstance(raw, (list, tuple)) else [raw]

    required_count = sum(1 for p in command.positional_args if p.required)
    if len(provided) < required_count:
        missing = [p for p in command.positional_args[len(provided):] if p.required]
        for m in missing:
            errors.append(ValidationError(
                kind="missing-positional",
                name=m.name,
                message=f'Required positional argument "{m.name}" is missing.',
            ))

    has_variadic = any(p.variadic for p in command.positional_args)
    if not has_variadic and len(provided) > len(command.positional_args):
        last = command.positional_args[-1].name if command.positional_args else "_"
        errors.append(ValidationError(
            kind="variadic-mismatch",
            name=last,
            message=f"Expected at most {len(command.positional_args)} positional argument(s) but received {len(provided)}.",
        ))
    return errors


def validate_options(command: ParsedCommand, options: dict[str, Any]) -> list[ValidationError]:
    lookup = _build_flag_lookup(command.flags)
    return [
        *_validate_flags(options, lookup),
        *_validate_positionals(options, command),
    ]


def validate_global_options(
    command: ParsedCommand, options: dict[str, Any]
) -> list[ValidationError]:
    """Validate a `_global` (pre-subcommand) options dict against the root command.

    Only per-key checks run — required-flag and positional checks don't apply
    to a partial dict of global options.
    """
    lookup = _build_flag_lookup(command.flags)
    return _validate_flags(options, lookup, check_required=False)
