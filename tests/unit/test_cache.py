import os
import tempfile
from pathlib import Path

import pytest

from cli_to_py import parse_help_text
from cli_to_py.cache import (
    cache_dir,
    clear_cache,
    load_cached_schema,
    save_cached_schema,
)
from cli_to_py.constants import CACHE_DIR_ENV
from tests.fixtures import REACT_GRAB_INIT_HELP


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path))
    yield tmp_path


def test_cache_dir_respects_env(temp_cache_dir):
    assert cache_dir() == temp_cache_dir


def test_save_and_load_roundtrip(temp_cache_dir):
    schema = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    path = save_cached_schema(schema)
    assert path.exists()
    loaded = load_cached_schema("grab")
    assert loaded is not None
    assert loaded.binary_name == "grab"
    assert len(loaded.command.flags) == len(schema.command.flags)
    first_flag_loaded = loaded.command.flags[0]
    first_flag_orig = schema.command.flags[0]
    assert first_flag_loaded.long_name == first_flag_orig.long_name


def test_load_returns_none_when_missing(temp_cache_dir):
    assert load_cached_schema("nonexistent-binary-xyz") is None


def test_clear_cache_removes_specific(temp_cache_dir):
    schema = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    save_cached_schema(schema)
    removed = clear_cache("grab")
    assert removed == 1
    assert load_cached_schema("grab") is None


def test_clear_cache_all(temp_cache_dir):
    schema1 = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    schema2 = parse_help_text("other", REACT_GRAB_INIT_HELP)
    save_cached_schema(schema1)
    save_cached_schema(schema2)
    removed = clear_cache()
    assert removed == 2


def test_corrupted_cache_returns_none(temp_cache_dir):
    schema = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    path = save_cached_schema(schema)
    path.write_text("not valid json {{{")
    assert load_cached_schema("grab") is None


def test_cache_path_sanitizes_binary_name(temp_cache_dir):
    """Regression: binary names with path separators must not escape cache_dir."""
    from cli_to_py.cache import _cache_path
    # Absolute path binary
    p1 = _cache_path("/usr/local/bin/uv")
    assert p1.parent == temp_cache_dir, f"{p1} escaped cache dir"
    assert "/" not in p1.name
    assert "uv" in p1.name

    # Relative path with traversal
    p2 = _cache_path("../../etc/passwd")
    assert p2.parent == temp_cache_dir
    assert ".." not in p2.name
    assert "passwd" in p2.name

    # Plain name still works
    p3 = _cache_path("git")
    assert p3.parent == temp_cache_dir
    assert p3.name.startswith("git-")


def test_preserves_nested_subcommand_data(temp_cache_dir):
    from cli_to_py.schema import CliSchema, ParsedCommand, ParsedFlag, ParsedSubcommand
    schema = CliSchema(
        binary_name="demo",
        command=ParsedCommand(
            name="demo",
            description="test",
            subcommands=[ParsedSubcommand(
                name="build",
                aliases=["b"],
                description="build it",
                flags=[ParsedFlag(
                    long_name="watch", short_name="-w", description="watch mode",
                    takes_value=False, value_name=None, default_value=None,
                    is_negated=False, is_required=False, choices=None,
                    uses_equals=False, is_global=False,
                )],
                positional_args=[],
            )],
        ),
    )
    save_cached_schema(schema)
    loaded = load_cached_schema("demo")
    assert loaded is not None
    assert loaded.command.subcommands[0].name == "build"
    assert loaded.command.subcommands[0].aliases == ["b"]
    assert loaded.command.subcommands[0].flags[0].long_name == "watch"
