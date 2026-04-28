# Quick Start

## Async API

```python
import asyncio
from cli_to_py import convert

async def main():
    uv = await convert("uv")

    result = await uv.add(_=["httpx"], dev=True)
    print(result.stdout)

    proc = await uv.spawn("sync", verbose=True)
    async for line in proc:
        print(line)

asyncio.run(main())
```

Keyword arguments become flags:

```python
api.command_string("commit", message="fix", all=True)
# git commit --message fix --all
```

Snake case becomes kebab case:

```python
await git.diff(name_only=True, _=["HEAD~1"])
# git diff --name-only HEAD~1
```

Single-character keyword arguments become short flags:

```python
api.command_string(n=True, _=["pattern"])
# grep -n pattern
```

## Sync API

```python
from cli_to_py import convert_sync

git = convert_sync("git")
result = git.status(short=True)
branch = git.branch(show_current=True).text()
```

## Static Help Text

Use static help text when you want parsing and validation without spawning a binary during conversion.

```python
from cli_to_py import from_help_text_sync

api = from_help_text_sync("mytool", """\
Usage: mytool [options] <file>

Options:
  -v, --verbose   enable verbose output
  --output <dir>  output directory
""")

errors = api.validate(outpt="./dist")
```
