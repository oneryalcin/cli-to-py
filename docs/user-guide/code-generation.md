# Code Generation

`cli-to-py` can generate standalone wrapper modules.

```bash
cli-to-py git -o git_wrapper.py
```

This writes:

- `git_wrapper.py`
- `git_wrapper.pyi`

Generated wrappers use only the Python standard library. They do not require `cli-to-py` at runtime.

```python
import git_wrapper

result = git_wrapper.status(short=True)
result = await git_wrapper.status_async(short=True)
```

Generated functions support the same call shapes as the live API, including
`_` for positionals and `_global` for pre-subcommand options:

```python
git_wrapper.log(_global={"C": "/path/to/repo"}, max_count=15)
# runs: git -C /path/to/repo log --max-count 15
```

## JSON and Stubs

```bash
cli-to-py git --json
cli-to-py git --stub
cli-to-py git --no-subcommands
```

`--no-subcommands` skips per-subcommand enrichment and is faster.

## Static Snapshot

Generated wrappers are a snapshot of the CLI help output at generation time. Regenerate after upgrading the underlying CLI if you want updated flags or subcommands.
