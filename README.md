# cli-to-py

A Python port of [`millionco/cli-to-js`](https://github.com/millionco/cli-to-js) — turn any CLI binary into a typed Python API, automatically.

Give it a binary name; it runs `--help`, parses the output into a schema, and hands you back an object where subcommands are methods, flags are kwargs, and calls can be validated before spawning.

```python
import asyncio
from cli_to_py import convert

async def main():
    git = await convert("git")

    # Subcommands become methods, flags become kwargs.
    result = await git.status(short=True)
    print(result.stdout)

    # Awaitable with .text() / .lines() / .json()
    branch  = await git.branch(show_current=True).text()
    changed = await git("diff", name_only=True, _=["HEAD~1"]).lines()

    # Validate BEFORE spawning — catch hallucinated flag names.
    errors = git.validate("commit", massage="fix")
    # -> [ValidationError(kind='unknown-flag',
    #                     suggestion='message',
    #                     message='Unknown flag "massage". Did you mean "message"?')]

    # Shell-safe string without executing.
    print(git.command_string("commit", message="fix", all=True))
    # -> git commit --message fix --all

    # Streaming via async iteration.
    proc = await git.spawn("log", oneline=True, n="10")
    async for line in proc:
        print(line)

asyncio.run(main())
```

Why it exists and how the whole thing works is covered in detail in [`notes.md`](notes.md). What follows is the user-facing documentation for the production package.

## Features

- **Async-first** via `asyncio.create_subprocess_exec`, with a full **sync mirror** (`convert_sync`, `SyncCliApi`) for non-async users.
- **Proxy-free Pythonic API** — just `__getattr__` + `__call__` on a regular class. No hidden traps, no parallel type file.
- **Awaitable with `.text()`, `.lines()`, `.json()`** via a lazy-task `CommandFuture`. Works both `await api.x()` and `await api.x().text()` on the same call.
- **Pre-spawn validation** with `difflib` did-you-mean suggestions (stdlib, no deps). Catches unknown flags, type mismatches, invalid choices, missing required flags, and missing positionals.
- **Streaming callbacks** (`on_stdout` / `on_stderr`) fire real-time per chunk in async mode, per-line in sync mode (post-completion). TTY-aware color forcing (`FORCE_COLOR` / `CLICOLOR_FORCE`) when streaming to a terminal.
- **`stdio="inherit"`** for interactive subcommands that need to pass through the parent terminal.
- **Per-call `RunConfig`** — `timeout`, `cwd`, `env` (merged with parent), `signal` (`asyncio.Event`-compatible cancellation).
- **Async iteration over process stdout** — `spawn_command` returns a `CommandProcess` supporting `async for line in proc:`.
- **Script chaining** — `script("cmd1", "cmd2").run()` composes commands with `&&`, stops on first failure.
- **`CommandTimeout`** carries `.partial_stdout` / `.partial_stderr` captured before the kill, so a caller can still see progress. Same for `CommandAborted` on signal cancellation.
- **`BinaryNotFoundError`** — typed `FileNotFoundError` subclass raised when the binary isn't on PATH.
- **Full process-group kill on POSIX** — `start_new_session=True` + `os.killpg(pgid, SIGKILL)` ensures shell-wrapped children (`sh -c "sleep 5"`) actually die on timeout instead of orphaning grandchildren.
- **Persistent schema cache** (opt-in) at `~/.cache/cli-to-py/`, keyed by `(binary name, resolved absolute path, mtime)` — auto-invalidates on upgrade. Filenames are sanitized against path traversal. Typical 10× speedup on warm calls for full-enrichment CLIs.
- **Code generation** — emit standalone Python wrapper modules (`.py` + `.pyi` stub) via `cli-to-py git -o git_wrapper.py`. The generated module has zero runtime dependencies on cli-to-py itself.
- **Zero runtime dependencies** — stdlib only (asyncio, re, dataclasses, difflib, shlex, json, subprocess, pathlib).

## Install

```bash
pip install cli-to-py
# or
uv add cli-to-py
```

Requires Python >= 3.11.

## Quick start

### Async usage

```python
import asyncio
from cli_to_py import convert

async def main():
    uv = await convert("uv")

    # Subcommand as method, flags as kwargs (snake_case → --kebab-case).
    result = await uv.add(_=["httpx"], dev=True)
    print(result.stdout)

    # Validate before spawning — 1-retry convergence for agents.
    errors = uv.validate("add", editble=True)  # typo
    # -> [ValidationError(kind='unknown-flag', suggestion='editable', ...),
    #     ValidationError(kind='missing-positional', name='REQUIREMENTS', ...)]

    # Iterate streaming output.
    proc = await uv.spawn("sync", verbose=True)
    async for line in proc:
        print(line)

asyncio.run(main())
```

### Sync usage

```python
from cli_to_py import convert_sync

git = convert_sync("git")
result = git.status(short=True)
branch = git.branch(show_current=True).text()
print(branch)
```

### Static help text (skip spawning)

Use `from_help_text_sync` to get a sync API, or `from_help_text` for async.
Both build from a pre-captured help-text string without spawning the binary.

```python
from cli_to_py import from_help_text_sync

api = from_help_text_sync("mytool", """\
Usage: mytool [options] <file>

Options:
  -v, --verbose   enable verbose output
  --output <dir>  output directory
""")

# Pure validation (no subprocess):
errors = api.validate(outpt="./dist")
# -> [ValidationError(kind='unknown-flag', suggestion='output', ...)]

# If the binary is also on PATH, dispatched methods still run it:
result = api(version=True)   # -> runs `mytool --version`
```

## `RunConfig` — per-call execution control

```python
from cli_to_py import RunConfig, convert
import asyncio

async def main():
    git = await convert("git", default_config=RunConfig(timeout=60.0))

    # Override per call.
    cfg = RunConfig(
        cwd="/tmp/workspace",
        env={"GIT_AUTHOR_NAME": "bot"},
        timeout=10.0,
        on_stdout=lambda chunk: print(f"stdout: {chunk}", end=""),
        on_stderr=lambda chunk: print(f"stderr: {chunk}", end=""),
    )
    await git.commit(message="auto", _config=cfg)

    # Cancellation via asyncio.Event.
    stop = asyncio.Event()
    cfg = RunConfig(signal=stop, timeout=300.0)
    task = asyncio.create_task(git.fetch(_config=cfg))
    await asyncio.sleep(1)
    stop.set()  # aborts the subprocess

asyncio.run(main())
```

## `stdio="inherit"` — interactive subcommands

```python
cfg = RunConfig(stdio="inherit")
await api.login(_config=cfg)  # tty passes through to the child
```

## Script chaining

```python
from cli_to_py import script

deploy = script(
    "git add -A",
    "git commit -m deploy",
    "git push",
)
print(deploy)                  # "git add -A && git commit -m deploy && git push"
result = await deploy.run()     # async
result = deploy.run_sync()      # sync
```

## Schema caching

Cold conversion of a multi-subcommand CLI like `git` or `uv` takes ~300–1500ms because each subcommand requires its own `--help` spawn. Enable the cache to make warm calls near-instant:

```python
# First call populates the cache (~1s for git with subcommand enrichment).
git = await convert("git", use_cache=True)

# Subsequent calls read from ~/.cache/cli-to-py/ (~10-30ms).
git = await convert("git", use_cache=True)
```

Cache keys are `sha1(binary_name | shutil.which(binary_name) | mtime)`, so
upgrading the binary (or moving it to a different location on PATH) auto-
matically invalidates the entry. If the binary can't be resolved via
`shutil.which`, the cache key falls back to `sha1(binary_name)` — meaning
two different CLIs with the same relative name but different cwds would
share a cache entry. Prefer absolute paths or installed binaries when
caching matters.

Override the cache location with `CLI_TO_PY_CACHE_DIR=/tmp/my-cache`. The
filename portion of each cache entry is the binary's basename (stripped of
path separators) + a hash suffix, so `convert("/usr/local/bin/uv")` writes
to `~/.cache/cli-to-py/uv-<hash>.json`, not to `/usr/local/bin/uv-*.json`.

```python
from cli_to_py import clear_cache
clear_cache()               # remove all cached schemas
clear_cache("git")           # remove just git
```

## CLI entry point — generate standalone wrappers

```bash
# Generate a wrapper module with zero cli-to-py dependency
cli-to-py git -o git_wrapper.py

# Wrote git_wrapper.py
# Wrote git_wrapper.pyi       ← type stub auto-generated alongside

cli-to-py git --json          # dump raw schema as JSON
cli-to-py git --stub          # emit only the .pyi
cli-to-py git --no-subcommands   # skip subcommand enrichment (faster)
cli-to-py --clear-cache        # wipe ~/.cache/cli-to-py/
```

The generated `.py` file embeds a tiny `_run_sync` / `_run_async` helper and exports a function per subcommand. Drop into any project, no deps:

```python
# generated git_wrapper.py
import git_wrapper

result = git_wrapper.status(short=True)         # sync
result = await git_wrapper.status_async(short=True)  # async
```

## Public API surface

| Symbol | Purpose |
|---|---|
| `convert(binary, ...)` | async: spawn --help, parse, enrich → `CliApi` |
| `convert_sync(binary, ...)` | sync variant → `SyncCliApi` |
| `from_help_text(name, text)` / `from_help_text_sync` | build from static text |
| `CliApi` / `SyncCliApi` | the returned dispatch objects |
| `CommandFuture` | awaitable + `.text()` / `.lines()` / `.json()` |
| `CommandProcess` | streaming: `async for line in proc` |
| `RunConfig` | per-call execution config |
| `run_command` / `run_command_sync` | low-level runners |
| `spawn_command` | low-level streaming spawn |
| `parse_help_text(name, text)` | pure text → CliSchema |
| `validate_options(command, opts)` | pure validator → `list[ValidationError]` |
| `options_to_args(dict)` | pure kwargs → argv |
| `to_command_string(bin, subs, opts)` | pure kwargs → shell string |
| `script(*steps)` | chain commands with `&&` |
| `Script.run()` / `Script.run_sync()` | execute a chain |
| `generate_wrapper(schema)` | emit standalone .py |
| `generate_stub(schema)` | emit standalone .pyi |
| `generate_json(schema)` | emit JSON schema dump |
| `load_cached_schema` / `save_cached_schema` / `clear_cache` / `cache_dir` | cache internals |
| `ValidationError` | dataclass with `kind`, `name`, `message`, `suggestion`, `choices` |

## Parser coverage / limitations

The help-text parser is a line-by-line state machine tuned for the common
formats produced by Commander.js, clap, click, cobra, and argparse. It
handles:

- Usage lines, positional args, section headers (`Options:`, `Commands:`,
  `Arguments:`, `Sub-commands:`, `Global options:`, etc).
- Short + long flags, wrapped descriptions, defaults, `[required]`,
  enum choices (`{a,b,c}` or `(choices: a,b,c)`), `[no-]` negation.
- Optional-value long flags: `--color[=WHEN]`.
- No-space short-flag values: `-v<level>`.
- Recursive subcommand enrichment up to depth 3 (`uv pip install` works).

Known misses / silent degradation:

- Multi-column help layouts that split one option across 3+ columns
  (Python's own `python --help` is an example). The parser returns an
  empty flag list rather than crashing; `validate()` will then produce
  false-positive `unknown-flag` errors. `from_help_text(...)` lets you
  feed pre-normalized text as a workaround.
- Hand-rolled help with non-standard section headers or no section
  headers at all. In this case all flags land in the root section, which
  usually still works for validation.
- Inline values with shell-special chars in the placeholder
  (`--path /foo/bar`): the value name is stripped to `[\w.-]`, so
  display only — argv construction still passes the real value through.

If you hit a CLI the parser mishandles, the escape hatch is
`convert(..., subcommands=False)` + `api.parse("subcmd")` for targeted
lazy enrichment, or `from_help_text(binary, captured_text)` to feed
cleaned-up help.

## Error correction for agents

The killer feature. Pre-spawn validation + Levenshtein-like did-you-mean suggestions:

```python
errors = uv.validate("add", editble=True, dveelopment=True)
for err in errors:
    print(f"{err.kind}: {err.message}")
    if err.suggestion:
        print(f"  -> did you mean: {err.suggestion}")
```

```
unknown-flag: Unknown flag "editble". Did you mean "editable"?
  -> did you mean: editable
unknown-flag: Unknown flag "dveelopment". Did you mean "development"?
  -> did you mean: development
missing-positional: Required positional argument "REQUIREMENTS" is missing.
```

Three structured errors, actionable suggestions, **zero** subprocesses spawned. An agent reads the errors, rewrites the call, and converges in one retry — instead of fighting against raw stderr for several turns.

Six error kinds: `unknown-flag`, `type-mismatch`, `invalid-choice`, `missing-required-flag`, `missing-positional`, `variadic-mismatch`.

## Development

```bash
uv sync                              # install dev deps
uv run pytest tests/                 # full test suite (204 tests)
uv run pytest tests/unit -q          # fast unit tests only (154)
uv run pytest tests/integration -q   # end-to-end with real binaries (50)
uv run python smoke_test.py          # interactive smoke walkthrough
uv build                             # build wheel + sdist
```

### Layout

```
cli_to_py/
├── __init__.py           # re-exports
├── constants.py          # magic numbers
├── schema.py             # dataclasses (CliSchema, ParsedFlag, CommandResult)
├── case.py               # snake_to_kebab / kebab_to_snake
├── options_to_args.py    # dict → argv
├── best_help.py          # pick stdout vs stderr
├── parse_help.py         # help-text parser (state machine)
├── parse_subcommands.py  # recursive enrichment (depth-aware)
├── load_schema.py        # orchestrator
├── env_utils.py          # shared env / color-detect (exec + sync_exec)
├── exec.py               # async run_command / spawn_command
├── sync_exec.py          # sync equivalents (Popen-based)
├── run_config.py         # RunConfig dataclass + merge
├── validate.py           # validation with did-you-mean
├── command_future.py     # awaitable CommandResult wrapper
├── command_string.py     # shell string serialization
├── _api_base.py          # _BaseCliApi (shared dispatch plumbing)
├── api.py                # CliApi (async)
├── sync_api.py           # SyncCliApi
├── script.py             # Script chain
├── cache.py              # persistent schema cache
├── generate.py           # codegen (.py + .pyi)
├── cli.py                # cli-to-py entry point
└── convert.py            # convert / convert_sync / from_help_text

tests/
├── unit/                 # 154 tests, pure text/logic
└── integration/          # 50 tests, real binaries + subprocess + wheel e2e
```

## Research provenance

This project started as [research notes](./notes.md) on `millionco/cli-to-js`, then a single-file prototype (`cli_to_py.py`), and was promoted to a production package over the iterations in git history:

- **iter 1**: split single-file prototype into package + `pyproject.toml`
- **iter 2**: build full pytest suite covering every module
- **iter 3–8**: tests for sync API, streaming, env/cwd, RunConfig, script, color, cache, codegen
- **iter 9**: black-box CLI subprocess + wheel install e2e
- **iter 10**: smoke test + documentation
- **fix-iter A**: P0 correctness (RunConfig merge, grandchild-deadlock, cache path sanitization)
- **fix-iter B**: API design (`__getattr__` discipline, nested enrichment, shared plumbing)
- **fix-iter C**: dead-code cuts (`from_kwargs`, exclusive-flag machinery, `_SyncCommandResult`)
- **fix-iter D**: parser edge cases + documentation

The original architectural exploration (in 6 parts) is preserved in `notes.md` for anyone learning the parser state-machine or the proxy/`__getattr__` pattern.

## License

MIT
