"""Command-line entry point for cli-to-py.

Usage:
    cli-to-py git                           # dump generated wrapper to stdout
    cli-to-py git -o git_wrapper.py         # write to file (+ git_wrapper.pyi)
    cli-to-py git --json                    # dump raw schema as JSON
    cli-to-py git --stub -o git.pyi         # stub only
    cli-to-py git --subcommands              # enrich each subcommand's flags
    cli-to-py git --no-subcommands          # skip enrichment (faster)
    cli-to-py --clear-cache                 # remove all cached schemas
    cli-to-py --clear-cache git             # remove just git's cache
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .cache import clear_cache
from .generate import generate_json, generate_stub, generate_wrapper
from .load_schema import load_schema


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli-to-py",
        description="Turn any CLI into a Python API, automatically.",
    )
    parser.add_argument("binary", nargs="?", help="CLI binary to convert")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="write to file instead of stdout (also emits <file>.pyi stub)",
    )
    parser.add_argument("--json", action="store_true", help="dump parsed schema as JSON")
    parser.add_argument("--stub", action="store_true", help="emit only the .pyi type stub")
    parser.add_argument(
        "--subcommands", dest="subcommands", action="store_true", default=True,
        help="parse subcommand help texts (default)",
    )
    parser.add_argument(
        "--no-subcommands", dest="subcommands", action="store_false",
        help="skip subcommand enrichment (faster)",
    )
    parser.add_argument("--help-flag", default="--help", help='flag to fetch help (default "--help")')
    parser.add_argument("--timeout", type=float, default=10.0, help="help-fetch timeout (seconds)")
    parser.add_argument("--clear-cache", action="store_true", help="clear cached schemas and exit")
    return parser


async def _load(binary: str, subcommands: bool, help_flag: str, timeout: float):
    return await load_schema(
        binary, help_flag=help_flag, timeout=timeout, subcommands=subcommands,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.clear_cache:
        removed = clear_cache(args.binary if args.binary else None)
        print(f"Cleared {removed} cache entries.")
        return 0

    if args.binary is None:
        parser.error("binary is required (unless using --clear-cache)")

    try:
        schema = asyncio.run(_load(args.binary, args.subcommands, args.help_flag, args.timeout))
    except FileNotFoundError:
        print(f"cli-to-py: binary not found: {args.binary}", file=sys.stderr)
        return 2
    except Exception as err:
        print(f"cli-to-py: failed to load {args.binary}: {err}", file=sys.stderr)
        return 1

    if args.json:
        output = generate_json(schema)
    elif args.stub:
        output = generate_stub(schema)
    else:
        output = generate_wrapper(schema)

    if args.output:
        args.output.write_text(output)
        print(f"Wrote {args.output}")
        if not args.json and not args.stub:
            stub_path = args.output.with_suffix(".pyi")
            stub_path.write_text(generate_stub(schema))
            print(f"Wrote {stub_path}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
