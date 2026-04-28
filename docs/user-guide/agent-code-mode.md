# Agent Code Mode

`cli-to-py` is useful for normal Python applications, but the main design target
is agent code that needs to coordinate CLI tools.

## The Problem

Traditional tool calling is sequential. An agent asks for one tool call, waits
for the result, reasons in text, then asks for another tool call.

That gets clumsy when the task needs:

- loops over many files or records
- arithmetic or aggregation
- branching based on command output
- retries and filtering
- many calls to the same CLI
- coordination across several CLIs

Python is a better control plane for that work.

## The Pattern

Use `cli-to-py` to convert a CLI into a Python object:

```python
from cli_to_py import convert

git = await convert("git")
```

Then expose selected operations to the agent's code runtime:

```python
async def changed_python_files(base: str = "HEAD~1") -> list[str]:
    paths = await git("diff", name_only=True, _=[base]).lines()
    return [path for path in paths if path.endswith(".py")]

async def last_commit_for_file(path: str) -> str:
    return await git("log", oneline=True, n=1, _=["--", path]).text()
```

An agent can then write ordinary Python to coordinate those functions:

```python
files = await changed_python_files("HEAD~5")
for path in files:
    print(path, await last_commit_for_file(path))
```

The result is fewer round trips and less text reasoning for work that is really
program control flow.

## Interpreter Fit

Interpreters such as [Monty](https://github.com/pydantic/monty) are designed for
agent-written Python with host-provided external functions. `cli-to-py` fits as
the adapter layer between command-line tools and those host functions.

The split is:

- `cli-to-py` converts CLI help and process execution into Python callables.
- The host application chooses which functions are exposed.
- The interpreter runs agent-written Python against that controlled function set.

`cli-to-py` is not a sandbox. Use the interpreter or host application to enforce
resource limits, filesystem policy, network policy, and authorization.

## Why Validation Matters

Agent-written code can typo a flag or invent an option. Validation lets the host
check calls before spawning a subprocess:

```python
errors = git.validate("commit", massage="fix")
assert errors[0].suggestion == "message"
```

That makes retries cheaper: the agent can repair structured validation errors
instead of parsing arbitrary CLI stderr.
