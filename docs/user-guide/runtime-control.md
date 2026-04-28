# Runtime Control

Use `RunConfig` to control subprocess execution.

```python
from cli_to_py import RunConfig, convert

git = await convert("git", default_config=RunConfig(timeout=60.0))

cfg = RunConfig(
    cwd="/tmp/workspace",
    env={"GIT_AUTHOR_NAME": "bot"},
    timeout=10.0,
)

await git.commit(message="auto", _config=cfg)
```

## Streaming Callbacks

```python
cfg = RunConfig(
    on_stdout=lambda chunk: print(chunk, end=""),
    on_stderr=lambda chunk: print(chunk, end=""),
)

await api.build(_config=cfg)
```

Async callbacks fire while the process is running. Sync callbacks fire after process completion.

## Async Iteration

```python
proc = await git.spawn("log", oneline=True)
async for line in proc:
    print(line)
```

## Interactive Commands

```python
cfg = RunConfig(stdio="inherit")
await api.login(_config=cfg)
```

## Cancellation

```python
import asyncio
from cli_to_py import RunConfig

stop = asyncio.Event()
task = asyncio.create_task(api.fetch(_config=RunConfig(signal=stop)))

stop.set()
await task
```

Timeouts and cancellations kill the full POSIX process group when possible, which helps avoid orphaned subprocess children.
