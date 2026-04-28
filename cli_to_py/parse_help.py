"""Parse CLI --help text into a CliSchema.

Ported from cli-to-js/src/parse-help-text.ts. See notes.md for the full
state-machine explanation. The algorithm:

1. Strip ANSI escapes.
2. Walk lines top-to-bottom, tracking which section we're in
   (usage / options / commands / arguments / unknown).
3. For each line, classify as: usage-line, section-header, flag-line,
   continuation-line, subcommand-line, or description-line.
4. Dispatch to the appropriate sub-parser.
5. Return the accumulated CliSchema.
"""

from __future__ import annotations

import re

from .constants import COLUMN_SEPARATOR_MIN_SPACES, DESCRIPTION_CONTINUATION_INDENT_MIN
from .schema import CliSchema, ParsedCommand, ParsedFlag, ParsedPositionalArg, ParsedSubcommand

_ANSI_RE = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\].*?(?:\x07|\x1B\\))")
_USAGE_RE = re.compile(r"usage:\s*(\S+)(.*)", re.IGNORECASE)
# Accept letters / digits / hyphens / spaces / parens in section headers
# (e.g. "Sub-commands:", "IO (v2):", "Cache options:").
_SECTION_HEADER_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9\s\-()]*?)\s*:\s*$")
_FLAG_START_RE = re.compile(r"^\s+-")
_CONTINUATION_RE = re.compile(rf"^\s{{{DESCRIPTION_CONTINUATION_INDENT_MIN},}}\S")
_COLUMN_SEPARATOR_RE = re.compile(rf"^(.+?)\s{{{COLUMN_SEPARATOR_MIN_SPACES},}}(.+)$")
_CURLY_CHOICES_RE = re.compile(r"\{([^}]+)\}")
_DESC_CHOICES_RES = [
    re.compile(r"\((?:choices|values|one of):\s*([^)]+)\)", re.IGNORECASE),
    re.compile(r"\[(?:possible values|choices|options):\s*([^\]]+)\]", re.IGNORECASE),
]
_DEFAULT_RE = re.compile(r"\(default:\s*\"?([^)\"]*)\"?\)")
_REQUIRED_RE = re.compile(r"\(required\)|\[required\]", re.IGNORECASE)
_USAGE_POSITIONAL_RE = re.compile(
    r"(<([\w.\-]+)(?:\.\.\.)?>(\.\.\.)?|\[([\w.\-]+)(?:\.\.\.)?](\.\.\.)?)"
)

_COMMAND_LINE_WITH_DESC_RE = re.compile(
    rf"^([\w][\w-]*(?:\|[\w][\w-]*)*(?:\s+(?:\[.*?\]|<.*?>))*)"
    rf"\s{{{COLUMN_SEPARATOR_MIN_SPACES},}}(.+)$"
)
_COMMAND_LINE_NAMES_ONLY_RE = re.compile(r"^([\w][\w-]*(?:\|[\w][\w-]*)*)$")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _classify_section(header_text: str) -> str:
    lower = header_text.lower()
    if "global" in lower and ("option" in lower or "flag" in lower):
        return "global-options"
    if "option" in lower or "flag" in lower:
        return "options"
    if "command" in lower or "subcommand" in lower:
        return "commands"
    if "argument" in lower or "positional" in lower:
        return "arguments"
    return "unknown"


def _parse_choices(raw: str) -> list[str] | None:
    choices = [c.strip() for c in re.split(r"[,|]", raw) if c.strip()]
    return choices or None


def _extract_choices(text: str) -> list[str] | None:
    match = _CURLY_CHOICES_RE.search(text)
    if match:
        return _parse_choices(match.group(1))
    for pattern in _DESC_CHOICES_RES:
        match = pattern.search(text)
        if match:
            return _parse_choices(match.group(1))
    return None


def _extract_default(description: str) -> str | None:
    match = _DEFAULT_RE.search(description)
    return match.group(1) if match else None


def _parse_flag_line(line: str) -> ParsedFlag | None:
    trimmed = line.strip()
    if not trimmed.startswith("-"):
        return None

    sep = _COLUMN_SEPARATOR_RE.match(trimmed)
    if sep:
        flag_part = sep.group(1).strip()
        description = sep.group(2).strip()
    else:
        flag_part = trimmed
        description = ""

    short_name: str | None = None
    long_name: str | None = None
    takes_value = False
    value_name: str | None = None
    uses_equals = False

    segments = [s.strip() for s in flag_part.split(",")]
    for raw_segment in segments:
        segment = raw_segment.replace("[no-]", "")
        if segment.startswith("--"):
            # Match optional `[=VALUE]`, then `=VALUE` / `<VALUE>` / ` VALUE`.
            # Group 1: long name. Group 2: separator (= or space). Group 3: value name.
            m = re.match(
                r"^(--[\w-]+)(?:\[?([=\s]+)[<\[]?([\w.\-]+)[>\]]?\]?)?",
                segment,
            )
            if m:
                long_name = m.group(1)[2:]
                if m.group(3):
                    takes_value = True
                    value_name = m.group(3)
                    if (m.group(2) or "").strip() == "=":
                        uses_equals = True
        elif segment.startswith("-"):
            # Short flag: -v, -v <val>, -v<val>, -v=<val>
            m = re.match(
                r"^(-\w)(?:(?:\s+|=)?[<\[]?([\w.\-]+)[>\]]?)?",
                segment,
            )
            if m:
                short_name = m.group(1)
                if m.group(2) and not takes_value:
                    takes_value = True
                    value_name = m.group(2)

    if not long_name and not short_name:
        return None
    if not long_name and short_name:
        long_name = short_name[1:]
    if not long_name:
        return None

    return ParsedFlag(
        long_name=long_name,
        short_name=short_name,
        description=description,
        takes_value=takes_value,
        value_name=value_name,
        default_value=_extract_default(description),
        is_negated=long_name.startswith("no-"),
        is_required=bool(_REQUIRED_RE.search(description)),
        choices=_extract_choices(flag_part) or _extract_choices(description),
        uses_equals=uses_equals,
        is_global=False,
    )


def _parse_command_line(line: str) -> ParsedSubcommand | None:
    trimmed = line.strip()
    if not trimmed or trimmed.startswith("-"):
        return None

    with_desc = _COMMAND_LINE_WITH_DESC_RE.match(trimmed)
    if with_desc:
        alias_match = re.match(r"^([\w][\w-]*(?:\|[\w][\w-]*)*)", with_desc.group(1))
        if not alias_match:
            return None
        all_names = alias_match.group(1).split("|")
        primary = all_names[0]
        if primary == "help":
            return None
        return ParsedSubcommand(
            name=primary,
            aliases=all_names[1:],
            description=with_desc.group(2).strip(),
        )

    names_only = _COMMAND_LINE_NAMES_ONLY_RE.match(trimmed)
    if names_only:
        all_names = names_only.group(1).split("|")
        primary = all_names[0]
        if primary == "help":
            return None
        return ParsedSubcommand(name=primary, aliases=all_names[1:], description="")

    return None


def _parse_usage_positionals(line: str) -> list[ParsedPositionalArg]:
    match = _USAGE_RE.match(line) or _USAGE_RE.search(line)
    if not match:
        return []
    args_str = match.group(2)
    result: list[ParsedPositionalArg] = []
    for m in _USAGE_POSITIONAL_RE.finditer(args_str):
        full = m.group(0)
        is_required = full.startswith("<")
        name = m.group(2) or m.group(4)
        is_variadic = "..." in full
        if name in ("options", "command", "cmd", "OPTIONS", "COMMAND"):
            continue
        result.append(ParsedPositionalArg(name=name, required=is_required, variadic=is_variadic))
    return result


def parse_help_text(binary_name: str, help_text: str) -> CliSchema:
    cleaned = strip_ansi(help_text)
    lines = cleaned.split("\n")

    flags: list[ParsedFlag] = []
    subcommands: list[ParsedSubcommand] = []
    positional_args: list[ParsedPositionalArg] = []
    current_section = "unknown"
    seen_usage = False
    seen_first_section = False
    description_lines: list[str] = []

    for line in lines:
        if _USAGE_RE.match(line) or (not seen_usage and _USAGE_RE.search(line)):
            positional_args = _parse_usage_positionals(line)
            seen_usage = True
            continue

        header = _SECTION_HEADER_RE.match(line)
        if header:
            current_section = _classify_section(header.group(1))
            seen_first_section = True
            continue

        if seen_usage and not seen_first_section and line.strip() and not _FLAG_START_RE.match(line):
            description_lines.append(line.strip())
            continue

        is_options = current_section in ("options", "global-options", "unknown")

        if is_options and _FLAG_START_RE.match(line):
            flag = _parse_flag_line(line)
            if flag and flag.long_name not in ("help", "version", "h", "V"):
                if current_section == "global-options":
                    flag.is_global = True
                flags.append(flag)
        elif is_options and _CONTINUATION_RE.match(line) and line.strip() and flags:
            prev = flags[-1]
            prev.description += " " + line.strip()
            if not prev.default_value:
                prev.default_value = _extract_default(prev.description)
            if not prev.choices:
                prev.choices = _extract_choices(prev.description)
            if not prev.is_required:
                prev.is_required = bool(_REQUIRED_RE.search(prev.description))
        elif current_section == "commands" and line.strip() and not _FLAG_START_RE.match(line):
            if _CONTINUATION_RE.match(line) and subcommands:
                subcommands[-1].description += " " + line.strip()
            else:
                cmd = _parse_command_line(line)
                if cmd:
                    subcommands.append(cmd)

    return CliSchema(
        binary_name=binary_name,
        command=ParsedCommand(
            name=binary_name,
            description=" ".join(description_lines),
            flags=flags,
            positional_args=positional_args,
            subcommands=subcommands,
        ),
    )
