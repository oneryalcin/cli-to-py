"""Persistent schema cache for parsed CLI help text.

Rationale: parsing --help + enriching N subcommands costs ~300-1500ms per
binary. For frequently-used binaries (git, uv, kubectl), that adds up.
Cache the parsed CliSchema as JSON in ~/.cache/cli-to-py/, keyed by the
binary's absolute path + mtime, so cache invalidates when the binary is
upgraded.

The cache is optional and opt-in. Pass use_cache=True to convert() / convert_sync().
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .constants import CACHE_DEFAULT_SUBDIR, CACHE_DIR_ENV, CACHE_SCHEMA_VERSION
from .schema import CliSchema, ParsedCommand, ParsedFlag, ParsedPositionalArg, ParsedSubcommand


def cache_dir() -> Path:
    """Return the cache directory (respects CLI_TO_PY_CACHE_DIR env override)."""
    override = os.environ.get(CACHE_DIR_ENV)
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / CACHE_DEFAULT_SUBDIR
    return Path.home() / ".cache" / CACHE_DEFAULT_SUBDIR


def _resolve_binary(binary_name: str) -> Path | None:
    """Resolve binary to absolute path via shutil.which (or None if not found)."""
    found = shutil.which(binary_name)
    return Path(found) if found else None


def _cache_key(binary_name: str, *, subcommands: bool = True) -> str:
    """Build a cache key: hash of (absolute path, mtime, name, subcommands scope)."""
    resolved = _resolve_binary(binary_name)
    scope = "full" if subcommands else "root"
    if resolved is None:
        return hashlib.sha1(f"{binary_name}|{scope}".encode()).hexdigest()[:16]
    try:
        mtime = int(resolved.stat().st_mtime)
    except OSError:
        mtime = 0
    raw = f"{binary_name}|{resolved}|{mtime}|{scope}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_path(binary_name: str, *, subcommands: bool = True) -> Path:
    """Build a cache file path.

    The binary_name may contain path separators (e.g. '/usr/local/bin/uv' or
    './node_modules/.bin/foo'); strip them to a safe basename before embedding
    in the filename. Uniqueness comes from the hash, not the label.
    """
    safe_label = os.path.basename(binary_name).replace(os.sep, "_")
    if os.altsep:
        safe_label = safe_label.replace(os.altsep, "_")
    if not safe_label:
        safe_label = "bin"
    return cache_dir() / f"{safe_label}-{_cache_key(binary_name, subcommands=subcommands)}.json"


# ------------------------------------------------------------------ serialization

def _schema_to_dict(schema: CliSchema) -> dict[str, Any]:
    return {
        "version": CACHE_SCHEMA_VERSION,
        "binary_name": schema.binary_name,
        "command": dataclasses.asdict(schema.command),
    }


def _dict_to_command(d: dict[str, Any]) -> ParsedCommand:
    return ParsedCommand(
        name=d["name"],
        description=d.get("description", ""),
        flags=[ParsedFlag(**f) for f in d.get("flags", [])],
        positional_args=[ParsedPositionalArg(**p) for p in d.get("positional_args", [])],
        subcommands=[_dict_to_subcommand(s) for s in d.get("subcommands", [])],
    )


def _dict_to_subcommand(d: dict[str, Any]) -> ParsedSubcommand:
    flags = d.get("flags")
    positional = d.get("positional_args")
    subs = d.get("subcommands")
    return ParsedSubcommand(
        name=d["name"],
        aliases=d.get("aliases", []),
        description=d.get("description", ""),
        flags=[ParsedFlag(**f) for f in flags] if flags is not None else None,
        positional_args=[ParsedPositionalArg(**p) for p in positional] if positional is not None else None,
        subcommands=[_dict_to_subcommand(s) for s in subs] if subs else None,
    )


def _dict_to_schema(d: dict[str, Any]) -> CliSchema:
    if d.get("version") != CACHE_SCHEMA_VERSION:
        raise ValueError(f"cache schema version mismatch: {d.get('version')}")
    return CliSchema(
        binary_name=d["binary_name"],
        command=_dict_to_command(d["command"]),
    )


# ------------------------------------------------------------------ public

def load_cached_schema(binary_name: str, *, subcommands: bool = True) -> CliSchema | None:
    path = _cache_path(binary_name, subcommands=subcommands)
    if not path.exists():
        return None
    try:
        with path.open("r") as fh:
            data = json.load(fh)
        return _dict_to_schema(data)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
        return None


def save_cached_schema(schema: CliSchema, *, subcommands: bool = True) -> Path:
    path = _cache_path(schema.binary_name, subcommands=subcommands)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Per-process tmp suffix avoids concurrent writers racing the same .tmp file.
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        with tmp.open("w") as fh:
            json.dump(_schema_to_dict(schema), fh, indent=2)
        tmp.replace(path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return path


def clear_cache(binary_name: str | None = None) -> int:
    """Remove cached schemas. If binary_name is None, clear all. Returns count removed."""
    removed = 0
    base = cache_dir()
    if not base.exists():
        return 0
    if binary_name is not None:
        # Clear both subcommands=True and subcommands=False cache entries.
        for scope in (True, False):
            target = _cache_path(binary_name, subcommands=scope)
            if target.exists():
                target.unlink()
                removed += 1
        return removed
    for entry in base.iterdir():
        if entry.is_file() and entry.suffix == ".json":
            entry.unlink()
            removed += 1
    return removed
