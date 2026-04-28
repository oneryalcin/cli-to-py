# Installation

```bash
pip install cli-to-py
```

Or with uv:

```bash
uv add cli-to-py
```

Python 3.11 or newer is required.

## Development Install

From a checkout:

```bash
uv sync --extra dev
make test
```

Useful local commands:

```bash
make test
make build
make smoke
make publish-check
```

`make smoke` runs real local binaries and is intentionally not part of CI.
