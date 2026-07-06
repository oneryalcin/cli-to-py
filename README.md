# cli-to-py

[![PyPI version](https://img.shields.io/pypi/v/cli-to-py)](https://pypi.org/project/cli-to-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/cli-to-py)](https://pypi.org/project/cli-to-py/)
[![CI](https://github.com/oneryalcin/cli-to-py/actions/workflows/ci.yml/badge.svg)](https://github.com/oneryalcin/cli-to-py/actions/workflows/ci.yml)
[![Docs](https://github.com/oneryalcin/cli-to-py/actions/workflows/pages.yml/badge.svg)](https://github.com/oneryalcin/cli-to-py/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Turn CLI binaries into Python APIs for applications and LLM agents.

`cli-to-py` reads a command's help output, builds a callable Python wrapper, and
lets you run subcommands with keyword arguments instead of hand-built shell
strings.

Full documentation: <https://oneryalcin.github.io/cli-to-py/>

## Install

```bash
pip install cli-to-py
```

or:

```bash
uv add cli-to-py
```

Requires Python 3.11 or newer.

## Quick Start

```python
import asyncio
from cli_to_py import convert

async def main():
    git = await convert("git")

    result = await git.status(short=True)
    print(result.stdout)

    branch = await git.branch(show_current=True).text()
    changed = await git("diff", name_only=True, _=["HEAD~1"]).lines()

    print(branch)
    print(changed)

asyncio.run(main())
```

Flags use Python names and are converted to CLI flags:

```python
await git.commit(message="fix", all=True)
# runs: git commit --message fix --all
```

Use `_` for positional arguments:

```python
await git("diff", name_only=True, _=["HEAD~1"])
# runs: git diff --name-only HEAD~1
```

Use `_global` for options that must come **before** the subcommand
(`git -C`, `docker --context`, `kubectl --namespace`):

```python
await git("log", _global={"C": "/path/to/repo"}, max_count=15)
# runs: git -C /path/to/repo log --max-count 15
```

## Why It Exists

Traditional tool calling makes agents call tools one step at a time. That is
awkward when a task needs loops, branching, arithmetic, retries, filtering, or
many repeated CLI calls.

`cli-to-py` gives those CLIs a function-shaped Python interface. An agent can
write code that coordinates commands directly:

```python
git = await convert("git")

changed = await git("diff", name_only=True, _=["HEAD~1"]).lines()
for path in changed:
    if path.endswith(".py"):
        print(await git("log", oneline=True, n=1, _=["--", path]).text())
```

That pairs naturally with code-mode interpreters such as
[Monty](https://github.com/pydantic/monty), where host applications expose a
controlled set of functions and the agent writes Python to orchestrate them.

## Why Use It

- Convert CLIs into async Python APIs with no runtime dependencies.
- Expose command-line tools as functions for agent code-mode workflows.
- Validate flags and arguments before spawning a subprocess.
- Keep subprocess output ergonomic with `.text()`, `.lines()`, and `.json()`.
- Stream output, inherit stdio, set timeouts, pass env/cwd, and cancel work.
- Generate standalone wrapper modules for tools you want to check into a project.

## Documentation

- [Installation](https://oneryalcin.github.io/cli-to-py/getting-started/installation/)
- [Quick start](https://oneryalcin.github.io/cli-to-py/getting-started/quickstart/)
- [Agent code mode](https://oneryalcin.github.io/cli-to-py/user-guide/agent-code-mode/)
- [Validation](https://oneryalcin.github.io/cli-to-py/user-guide/validation/)
- [Runtime control](https://oneryalcin.github.io/cli-to-py/user-guide/runtime-control/)
- [Code generation](https://oneryalcin.github.io/cli-to-py/user-guide/code-generation/)
- [Parser limits](https://oneryalcin.github.io/cli-to-py/user-guide/parser-limits/)
- [Public API](https://oneryalcin.github.io/cli-to-py/api-reference/public-api/)

## CLI Wrapper Generation

Generate a dependency-free Python wrapper from a CLI:

```bash
cli-to-py git -o git_wrapper.py
```

The generated `.py` module and `.pyi` stub can be committed to another project
without depending on `cli-to-py` at runtime.

## Development

```bash
make test      # unit and integration tests
make ci        # full CI path, including package build
make docs      # strict MkDocs build
make build     # source distribution and wheel
```

See the [release checklist](https://oneryalcin.github.io/cli-to-py/development/release-checklist/)
for publishing steps.

## Status

This project parses common `--help` formats pragmatically. It is useful for many
CLIs, but it is not a formal parser for every help style. See
[parser limits](https://oneryalcin.github.io/cli-to-py/user-guide/parser-limits/)
before relying on generated wrappers for unusual CLIs.
