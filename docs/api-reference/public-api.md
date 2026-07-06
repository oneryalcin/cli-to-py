# Public API

| Symbol | Purpose |
| --- | --- |
| `convert(binary, ...)` | Async conversion from CLI help to `CliApi`. |
| `convert_sync(binary, ...)` | Sync conversion from CLI help to `SyncCliApi`. |
| `from_help_text(name, text)` | Async API from static help text. |
| `from_help_text_sync(name, text)` | Sync API from static help text. |
| `CliApi` | Async dispatch object. |
| `SyncCliApi` | Sync dispatch object. |
| `CommandFuture` | Awaitable command result with `.text()`, `.lines()`, `.json()`. |
| `CommandProcess` | Streaming process wrapper for async iteration. |
| `RunConfig` | Per-call execution config. |
| `run_command` | Low-level async command runner. |
| `run_command_sync` | Low-level sync command runner. |
| `spawn_command` | Low-level streaming spawn. |
| `parse_help_text` | Pure help text parser. |
| `validate_options` | Pure validator for parsed commands. |
| `validate_global_options` | Validator for `_global` (pre-subcommand) option dicts. |
| `options_to_args` | Convert kwargs to CLI argv. |
| `to_command_string` | Render a shell-safe command string. |
| `script` | Compose shell command chains. |
| `generate_wrapper` | Generate standalone `.py` wrapper code. |
| `generate_stub` | Generate standalone `.pyi` stub code. |
| `generate_json` | Dump parsed schema as JSON. |
| `clear_cache` | Remove schema cache entries. |

## Error Types

| Type | Purpose |
| --- | --- |
| `ValidationError` | Structured validation error. |
| `BinaryNotFoundError` | Raised when the binary cannot be found. |
| `CommandTimeout` | Raised on timeout; carries partial output. |
| `CommandAborted` | Raised on signal cancellation; carries partial output. |
