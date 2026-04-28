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
