"""Smoke test: exercise the full public API end-to-end against real binaries.

Run with:  uv run python smoke_test.py

This is not a unit test — it's the "does it actually work" walkthrough
for a reviewer. Prints progress to stdout and returns exit code 0 on
success.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cli_to_py import (
    CliApi,
    RunConfig,
    Script,
    SyncCliApi,
    cache_dir,
    clear_cache,
    convert,
    convert_sync,
    from_help_text,
    generate_stub,
    generate_wrapper,
    load_cached_schema,
    options_to_args,
    parse_help_text,
    run_command,
    script,
    spawn_command,
    validate_options,
)
from cli_to_py.constants import CACHE_DIR_ENV


FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    marker = "[ok]" if ok else "[FAIL]"
    print(f"  {marker} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILED.append(label)


def section(name: str) -> None:
    print(f"\n== {name} ==")


# --------------------------------------------------------------------- checks

def smoke_options_to_args() -> None:
    section("options_to_args")
    check("bool True", options_to_args({"verbose": True}) == ["--verbose"])
    check("snake_case -> kebab", options_to_args({"dry_run": True}) == ["--dry-run"])
    check("positional underscore", options_to_args({"_": ["file.txt"]}) == ["file.txt"])
    check("array repeats flag",
          options_to_args({"inc": ["a", "b"]}) == ["--inc", "a", "--inc", "b"])


def smoke_parse_help() -> None:
    section("parse_help_text")
    text = "Usage: foo [options]\n\nOptions:\n  -v, --verbose   enable verbose\n  --output <path>  where to write\n"
    schema = parse_help_text("foo", text)
    names = [f.long_name for f in schema.command.flags]
    check("parses verbose flag", "verbose" in names)
    check("parses output flag", "output" in names)
    out_flag = next(f for f in schema.command.flags if f.long_name == "output")
    check("detects takes_value", out_flag.takes_value is True)
    check("detects value_name", out_flag.value_name == "path")


def smoke_validation() -> None:
    section("validation + did-you-mean")
    text = "Usage: foo [options]\n\nOptions:\n  --message <m>  commit message\n  --all          stage all\n"
    schema = parse_help_text("foo", text)
    errors = validate_options(schema.command, {"massage": "x"})
    unknown = [e for e in errors if e.kind == "unknown-flag"]
    check("typo detected", len(unknown) == 1)
    check("suggestion provided", unknown[0].suggestion == "message" if unknown else False)


async def smoke_async_convert() -> None:
    section("convert() async")
    if shutil.which("git") is None:
        check("git not installed — skip", True, "")
        return
    api = await convert("git", subcommands=False)
    check("returns CliApi", isinstance(api, CliApi))
    check("binary_name", api.binary_name == "git")

    result = await api.status(short=True)
    check("git.status() runs", result.exit_code == 0)

    branch = await api.branch(show_current=True).text()
    check("branch().text() works", isinstance(branch, str) and len(branch) > 0, f"{branch!r}")


def smoke_sync_convert() -> None:
    section("convert_sync()")
    if shutil.which("git") is None:
        check("git not installed — skip", True, "")
        return
    api = convert_sync("git", subcommands=False)
    check("returns SyncCliApi", isinstance(api, SyncCliApi))
    result = api.status(short=True)
    check("sync status() runs", result.exit_code == 0)
    branch = api.branch(show_current=True).text()
    check("sync .text() works", isinstance(branch, str))


async def smoke_spawn_streaming() -> None:
    section("spawn_command() streaming")
    if shutil.which("sh") is None:
        check("sh not available — skip", True, "")
        return
    proc = await spawn_command("sh", ["-c", "for i in 1 2 3; do echo line $i; done"])
    lines = [line async for line in proc]
    code = await proc.exit_code()
    check("async iteration works", len(lines) == 3)
    check("exit code 0", code == 0)


async def smoke_streaming_callbacks() -> None:
    section("streaming callbacks")
    if shutil.which("sh") is None:
        check("sh not available — skip", True, "")
        return
    received: list[str] = []
    cfg = RunConfig(on_stdout=lambda chunk: received.append(chunk))
    result = await run_command("sh", ["-c", "echo realtime; echo feedback"], config=cfg)
    check("exit 0", result.exit_code == 0)
    check("callback fired", any("realtime" in chunk for chunk in received))


async def smoke_timeout() -> None:
    section("timeout")
    from cli_to_py.exec import CommandTimeout
    if shutil.which("sleep") is None:
        check("sleep not available — skip", True, "")
        return
    try:
        await run_command("sleep", ["5"], config=RunConfig(timeout=0.3))
        check("timeout raised", False, "no exception")
    except CommandTimeout:
        check("timeout raised", True)


def smoke_script_chaining() -> None:
    section("script() chaining")
    s = script("echo first", "echo second")
    check("str renders with &&", str(s) == "echo first && echo second")
    result = s.run_sync()
    check("chain runs", result.exit_code == 0 and "first" in result.stdout and "second" in result.stdout)

    fail = script("false", "echo unreachable")
    result = fail.run_sync()
    check("chain stops on failure", result.exit_code != 0 and "unreachable" not in result.stdout)


def smoke_cache(tmp_dir: Path) -> None:
    section("schema cache")
    os.environ[CACHE_DIR_ENV] = str(tmp_dir)
    clear_cache()
    check("cache dir respects env", cache_dir() == tmp_dir)

    if shutil.which("git") is None:
        check("git missing — skip round-trip", True, "")
        return

    # Cold populate, warm read
    api_cold = convert_sync("git", subcommands=False, use_cache=True)
    loaded = load_cached_schema("git", subcommands=False)
    check("cold write populates cache", loaded is not None)

    api_warm = convert_sync("git", subcommands=False, use_cache=True)
    check("warm read succeeds", api_warm.binary_name == "git")


def smoke_codegen(tmp_dir: Path) -> None:
    section("codegen")
    if shutil.which("git") is None:
        check("git missing — skip", True, "")
        return
    api = convert_sync("git", subcommands=False)
    code = generate_wrapper(api.schema)
    stub = generate_stub(api.schema)
    import ast
    try:
        ast.parse(code)
        check("wrapper is valid Python", True)
    except SyntaxError as err:
        check("wrapper is valid Python", False, str(err))
    try:
        ast.parse(stub)
        check("stub is valid Python", True)
    except SyntaxError as err:
        check("stub is valid Python", False, str(err))

    # Write and import
    wrapper_path = tmp_dir / "git_wrapper.py"
    wrapper_path.write_text(code)
    import importlib.util
    spec = importlib.util.spec_from_file_location("git_wrapper", str(wrapper_path))
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["git_wrapper"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    result = module.run(version=True)
    check("generated wrapper imports and runs", result.exit_code == 0)


def smoke_cli_entry(tmp_dir: Path) -> None:
    section("cli entry point")
    if shutil.which("git") is None:
        check("git missing — skip", True, "")
        return
    import subprocess
    output = tmp_dir / "git_wrapper_cli.py"
    result = subprocess.run(
        [sys.executable, "-m", "cli_to_py.cli", "git", "--no-subcommands", "-o", str(output)],
        capture_output=True,
        text=True,
    )
    check("cli-to-py cli exit 0", result.returncode == 0, result.stderr[:100])
    check("wrapper file written", output.exists())
    check("stub file written", output.with_suffix(".pyi").exists())


async def main() -> int:
    print("cli-to-py smoke test")
    print("====================")

    smoke_options_to_args()
    smoke_parse_help()
    smoke_validation()
    await smoke_async_convert()
    smoke_sync_convert()
    await smoke_spawn_streaming()
    await smoke_streaming_callbacks()
    await smoke_timeout()
    smoke_script_chaining()

    with tempfile.TemporaryDirectory() as td:
        smoke_cache(Path(td))

    with tempfile.TemporaryDirectory() as td:
        smoke_codegen(Path(td))

    with tempfile.TemporaryDirectory() as td:
        smoke_cli_entry(Path(td))

    print("\n" + "=" * 30)
    if FAILED:
        print(f"FAILED ({len(FAILED)}):")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
