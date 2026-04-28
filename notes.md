# cli-to-python research notes

## What cli-to-js does

Given a binary name, spawn `<bin> --help`, parse the resulting help text into a
schema (flags, subcommands, positional args, choices, required, aliases, etc),
then build a **Proxy-based** API where subcommands become methods and flags
become camelCase keyword options.

```ts
const git = await convertCliToJs("git");
const { stdout } = await git.diff({ nameOnly: true, _: ["HEAD~1"] });
```

## Module map (packages/cli-to-js/src/)

| File | Role |
|---|---|
| `index.ts` | Public exports: `convertCliToJs`, `fromHelpText` |
| `load-schema.ts` | Orchestrator: run --help, select best output, parse, enrich subcommands |
| `parse-help-text.ts` | Core text → schema parser (section detection, flag/cmd regex) |
| `parse-subcommands.ts` | Recursively re-run `<sub> --help` to fill in per-subcommand flags |
| `build-api.ts` | Build callable Proxy (root, $schema, $validate, $spawn, $command, $parse) |
| `exec.ts` | `runCommand` (buffered promise) + `spawnCommand` (streaming iterator) |
| `validate.ts` | Unknown-flag, type-mismatch, missing-required, exclusive-conflict with Levenshtein suggestions |
| `generate.ts` | Codegen: standalone .ts/.js wrapper files + .d.ts generator |
| `cli.ts` | `commander`-based CLI entry: `npx cli-to-js git -o git.ts` |
| `cli-api.ts` | TypeScript types for the Proxy-based API |
| `constants.ts` | Timeouts, indentation thresholds, magic numbers |
| `utils/options-to-args.ts` | Dict → argv: booleans → `--flag`, arrays → repeated, `_` → positionals |
| `utils/camel-to-kebab.ts`, `kebab-to-camel.ts` | Key name conversions |
| `utils/best-help-text.ts` | Pick stdout vs stderr by counting "usage/options/commands" signals |
| `utils/run-for-help.ts` | Dedicated spawn for `--help` (no options conversion) |
| `utils/parse-output.ts`, `enhance-promise.ts` | `.text()`, `.lines()`, `.json()` on returned promise |
| `utils/to-command-string.ts` | Serialize for `$command` shell string mode |
| `utils/levenshtein-distance.ts` | For did-you-mean suggestions |
| `utils/script.ts` | Compose multiple commands with `&&` sequential execution |

## Key data structures

```ts
CliSchema { binaryName, command: ParsedCommand }
ParsedCommand { name, description, flags[], positionalArgs[], subcommands[], mutuallyExclusiveFlags }
ParsedFlag { longName, shortName, description, takesValue, valueName, defaultValue,
             isNegated, isRequired, choices, usesEquals, isGlobal }
ParsedSubcommand { name, aliases[], description, flags?, positionalArgs?, subcommands? }
ParsedPositionalArg { name, required, variadic }
```

## Key insights for a Python port

1. **Python doesn't need Proxy gymnastics** — `__getattr__` + `__call__` on a class is cleaner than JS's Proxy.
2. **snake_case ↔ kebab-case** instead of camelCase ↔ kebab-case. Python idiomatic: `name_only=True` → `--name-only`.
3. **Positional args**: Python lets us use `*args` naturally — `git.diff("HEAD~1", name_only=True)` is cleaner than the JS `_: [...]` escape hatch. Keep `_` as fallback.
4. **Async-first** via `asyncio.create_subprocess_exec` — mirrors JS child_process. Also support sync via `subprocess.run`.
5. **Streaming iterator**: Python supports `async for line in proc:` natively via `__aiter__`.
6. **Awaitable with `.text()/.lines()/.json()`** — implement a class with `__await__` so it works both as `await` and as `(await .text())`.
7. **Validation**: dataclass `ValidationError`; Levenshtein via `difflib.get_close_matches` (stdlib!) — no third-party dep.
8. **Help text parsing**: biggest module; mostly pure text processing, translates 1:1 from TS.
9. **Codegen**: emit standalone .py files with embedded tiny `_run` helper + argparse-free API.

## Proposed package layout

```
cli_to_py/
├── __init__.py          # convert, from_help_text, run_command
├── schema.py            # ParsedFlag, ParsedCommand, CliSchema dataclasses
├── parse_help.py        # parse_help_text() → CliSchema
├── parse_subcommands.py # enrich_subcommands() recursively
├── load_schema.py       # orchestrator
├── exec.py              # run_command (async), spawn_command (async iter)
├── api.py               # CliApi class (__getattr__ + __call__)
├── validate.py          # validate_options(), ValidationError
├── generate.py          # emit standalone .py wrapper
├── cli.py               # argparse CLI entry point
├── constants.py         # magic nums
└── utils/
    ├── case.py          # snake_to_kebab, kebab_to_snake
    ├── options_to_args.py
    ├── best_help.py
    ├── run_for_help.py
    ├── command_string.py
    └── script.py
```

## Prototype plan

Build a minimal-but-working proof-of-concept in a single file `cli_to_py.py`:
- parse_help_text (core)
- options_to_args (snake_case → kebab flags)
- async run_command
- CliApi via __getattr__
- basic validation

Demonstrate end-to-end against a real binary (`git`, `uv`, `python -m pip`).

## Progress log

- [x] Cloned and mapped repo
- [x] Read all source files
- [x] Designed Python equivalent
- [ ] Build prototype
- [ ] Verify prototype against real binary
- [ ] Write final README
