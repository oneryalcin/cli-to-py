# Release Checklist

Run local checks:

```bash
make ci
make publish-check
```

Optional local smoke:

```bash
make smoke
```

Publish:

```bash
PYPI_TOKEN=... make publish
```

## Notes

- CI runs tests and build on Python 3.11, 3.12, 3.13, and 3.14.
- CI does not run `smoke_test.py` because it depends on local binaries and environment state.
- `make publish-check` is a dry-run publish check.
