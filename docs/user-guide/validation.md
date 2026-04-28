# Validation

Validation is explicit. Runtime calls do not automatically validate before spawning.

```python
errors = api.validate("commit", massage="fix")
if errors:
    print(errors[0].message)
    print(errors[0].suggestion)
else:
    await api.commit(message="fix")
```

Validation catches:

- unknown flags
- type mismatches
- invalid choices
- missing required flags
- missing required positionals
- too many positionals when the command is not variadic

## Why Manual

CLI help output is not standardized. Some tools omit flags, expose dynamic flags, or format help text in unusual ways. Manual validation gives agent and application code a safe preflight step without blocking legitimate escape hatches.

## Raw Flags

Raw keys that already start with `-` pass through unchanged:

```python
api.command_string(**{"-X": "POST"})
```

For normal use, prefer Python identifiers:

```python
api.command_string(name_only=True)
# --name-only
```
