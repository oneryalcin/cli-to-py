# Parser Limits

Help parsing is best-effort.

Most CLIs expose help as plain text, not as structured metadata. `cli-to-py` handles common patterns:

- `Usage:` lines
- `Options:` / `Flags:` sections
- `Commands:` / `Subcommands:` sections
- short and long flags
- value placeholders such as `--output <path>`
- choices such as `{low,medium,high}`
- wrapped descriptions

## Known Limits

- Undocumented flags cannot be validated.
- Dynamic flags may not appear in help output.
- Deep nested command trees are parsed into the schema, but runtime dispatch is currently one-level.
- Some CLIs use custom help layouts that may parse only partially.

Use raw dash-prefixed keys as an escape hatch when needed:

```python
await api(**{"--experimental-flag": True, "_": ["value"]})
```

Or bypass validation for a command and let the underlying CLI decide.

## Global (Pre-Subcommand) Options

Regular kwargs render after the subcommand. Options that a CLI requires
**before** the subcommand — `git -C <path>`, `docker --context`,
`kubectl --namespace`, `terraform -chdir` — go in the reserved `_global`
dict:

```python
await git("log", _global={"C": "/path/to/repo"}, max_count=15)
# runs: git -C /path/to/repo log --max-count 15
```

`_global` uses the same rendering rules as regular kwargs (short flags,
kebab-casing, booleans, lists, raw dash-prefixed keys) and works with
`__call__`, dot dispatch, `spawn`, `command_string`, and `validate` on both
the async and sync APIs. Positionals (`_`) are not allowed inside it.
