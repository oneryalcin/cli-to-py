"""Convert a Python kwargs dict into CLI argv.

Conventions (mirrors cli-to-js/src/utils/options-to-args.ts):

    verbose=True         -> --verbose
    verbose=False        -> omitted
    output="f.txt"       -> --output f.txt
    dry_run=True         -> --dry-run
    include=["a", "b"]   -> --include a --include b
    _=["pos1", "pos2"]   -> pos1 pos2
    v=True               -> -v           (single-char keys become short flags)
    msg="hi" with equals -> --msg=hi     (for flags that use key=value form)

Raw keys that already start with "-" are passed through unchanged
(escape hatch for flags whose canonical form would otherwise be re-cased).
"""

from __future__ import annotations

from typing import Any

from .case import snake_to_kebab
from .constants import SHORT_FLAG_MAX_LENGTH


def options_to_args(
    options: dict[str, Any] | None,
    equals_flags: set[str] | None = None,
) -> list[str]:
    if options is None:
        return []
    equals_flags = equals_flags or set()

    flag_args: list[str] = []
    positional_args: list[str] = []

    for key, value in options.items():
        if key == "_":
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            positional_args.extend(str(item) for item in items)
            continue

        if key.startswith("-"):
            flag_name = key
        elif len(key) <= SHORT_FLAG_MAX_LENGTH:
            flag_name = f"-{key}"
        else:
            flag_name = f"--{snake_to_kebab(key)}"

        use_equals = key in equals_flags

        if isinstance(value, bool):
            if value:
                flag_args.append(flag_name)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if use_equals:
                    flag_args.append(f"{flag_name}={item}")
                else:
                    flag_args.extend([flag_name, str(item)])
        elif value is not None:
            if use_equals:
                flag_args.append(f"{flag_name}={value}")
            else:
                flag_args.extend([flag_name, str(value)])

    return flag_args + positional_args
