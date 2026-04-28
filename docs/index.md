# cli-to-py

Turn CLI binaries into Python APIs.

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

## What It Provides

- Async-first API with a sync mirror.
- Pythonic dispatch: `api.status(short=True)` becomes `git status --short`.
- Manual pre-spawn validation for typo-prone flags.
- Streaming, timeouts, cancellation, cwd/env overrides, and interactive stdio.
- Optional schema cache for faster repeated conversion.
- Standalone wrapper generation with `.py` and `.pyi` output.
- Zero runtime dependencies.

## Documentation

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Validation](user-guide/validation.md)
- [Runtime Control](user-guide/runtime-control.md)
- [Code Generation](user-guide/code-generation.md)
- [Public API](api-reference/public-api.md)

## Status

Alpha. The core runtime paths are tested, but help parsing is necessarily best-effort because CLI help formats are not standardized.
