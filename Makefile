UV ?= uv --no-config
PYTEST ?= python -m pytest
PYPI_CHECK_URL ?= https://pypi.org/simple/

.PHONY: help test test-unit test-integration build clean ci smoke publish-check publish

help:
	@printf '%s\n' \
		'Targets:' \
		'  make test              Run unit and integration tests' \
		'  make test-unit         Run unit tests only' \
		'  make test-integration  Run integration tests only' \
		'  make build             Build sdist and wheel' \
		'  make ci                Run CI-equivalent checks except matrix Python' \
		'  make smoke             Run local smoke script (not used in CI)' \
		'  make clean             Remove local generated artifacts' \
		'  make publish-check     Dry-run publish built artifacts' \
		'  make publish           Publish built artifacts to PyPI'

test:
	$(UV) run --locked --extra dev $(PYTEST) -q

test-unit:
	$(UV) run --locked --extra dev $(PYTEST) tests/unit -q

test-integration:
	$(UV) run --locked --extra dev $(PYTEST) tests/integration -q

build:
	$(UV) build

ci: test build

smoke:
	$(UV) run --locked python smoke_test.py

clean:
	rm -rf .pytest_cache dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

publish-check: build
	@if [ -n "$$PYPI_TOKEN" ]; then \
		UV_PUBLISH_TOKEN="$$PYPI_TOKEN" $(UV) publish --dry-run --check-url $(PYPI_CHECK_URL) dist/*; \
	else \
		$(UV) publish --dry-run --check-url $(PYPI_CHECK_URL) dist/*; \
	fi

publish: build
	@test -n "$(PYPI_TOKEN)" || (printf '%s\n' 'PYPI_TOKEN is required' >&2; exit 1)
	@UV_PUBLISH_TOKEN="$(PYPI_TOKEN)" $(UV) publish --check-url $(PYPI_CHECK_URL) dist/*
