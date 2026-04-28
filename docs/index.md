# cli-to-py

Turn CLI binaries into Python APIs for applications and LLM agents.

`cli-to-py` reads a command's help output, builds a schema, and returns a Python object where subcommands are methods and CLI flags are keyword arguments.

```python
import asyncio
from cli_to_py import convert

async def main():
    git = await convert("git")

    result = await git.status(short=True)
    print(result.stdout)

    branch = await git.branch(show_current=True).text()
    changed = await git("diff", name_only=True, _=["HEAD~1"]).lines()

    errors = git.validate("commit", massage="fix")
    print(errors[0].suggestion)  # "message"

asyncio.run(main())
```

## Why It Exists

LLM agents often need to coordinate command-line tools repeatedly: loop over
files, calculate intermediate values, branch on results, retry failures, and
combine several tools into one workflow.

Sequential tool calls are a poor fit for that. Code is a better control plane.
`cli-to-py` makes CLIs available as Python functions so an agent can write code
that coordinates them.

This works well with code-mode interpreters such as
[Monty](https://github.com/pydantic/monty): the interpreter runs agent-written
Python, while the host application decides which converted CLI functions are
available.

## What It Provides

- Async-first API with a sync mirror.
- Pythonic dispatch: `api.status(short=True)` becomes `git status --short`.
- Function-shaped CLI access for agent code-mode workflows.
- Manual pre-spawn validation for typo-prone flags.
- Streaming, timeouts, cancellation, cwd/env overrides, and interactive stdio.
- Optional schema cache for faster repeated conversion.
- Standalone wrapper generation with `.py` and `.pyi` output.
- Zero runtime dependencies.

## Documentation

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Agent Code Mode](user-guide/agent-code-mode.md)
- [Validation](user-guide/validation.md)
- [Runtime Control](user-guide/runtime-control.md)
- [Code Generation](user-guide/code-generation.md)
- [Public API](api-reference/public-api.md)

## Status

Alpha. The core runtime paths are tested, but help parsing is necessarily best-effort because CLI help formats are not standardized.
