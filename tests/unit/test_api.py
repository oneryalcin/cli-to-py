"""Unit tests for CliApi and SyncCliApi attribute-dispatch semantics.

Uses fromHelpText so we don't depend on real binaries. Exercises:
- __getattr__ returning a dispatcher
- __call__ with subcommand positional arg
- validate() via subcommand name
- command_string() for shell strings
- alias resolution
- reserved attrs (binary_name, schema) still work
"""

from cli_to_py import from_help_text, from_help_text_sync
from tests.fixtures import REACT_GRAB_HELP, REACT_GRAB_INIT_HELP


def test_api_exposes_binary_name():
    api = from_help_text("grab", REACT_GRAB_HELP)
    assert api.binary_name == "grab"


def test_api_exposes_schema():
    api = from_help_text("grab", REACT_GRAB_HELP)
    assert api.schema.binary_name == "grab"
    assert len(api.schema.command.subcommands) > 0


def test_alias_resolution():
    api = from_help_text("grab", REACT_GRAB_HELP)
    # "setup" is an alias for "init"
    assert api._resolve_alias("setup") == "init"
    assert api._resolve_alias("install") == "add"
    assert api._resolve_alias("nonexistent") == "nonexistent"


def test_command_string_uses_alias():
    api = from_help_text("grab", REACT_GRAB_HELP)
    cmd = api.command_string("setup")
    # setup -> init
    assert cmd == "grab init"


def test_command_string_root():
    api = from_help_text("grab", REACT_GRAB_HELP)
    cmd = api.command_string()
    assert cmd == "grab"


def test_command_string_with_flags():
    api = from_help_text("grab", REACT_GRAB_INIT_HELP)
    cmd = api.command_string(key="abc123", force=True)
    assert "grab" in cmd
    assert "--key" in cmd
    assert "abc123" in cmd
    assert "--force" in cmd


def test_getattr_returns_callable():
    api = from_help_text("grab", REACT_GRAB_HELP)
    dispatcher = api.init
    assert callable(dispatcher)


def test_validate_root_options():
    api = from_help_text("grab", REACT_GRAB_INIT_HELP)
    errors = api.validate(nonexistent_flag=True)
    assert any(e.kind == "unknown-flag" for e in errors)


def test_sync_api_same_surface():
    api = from_help_text_sync("grab", REACT_GRAB_HELP)
    assert api.binary_name == "grab"
    assert callable(api.init)
    assert api.command_string("init") == "grab init"


class TestGetattrDiscipline:
    """Regression: hasattr() / getattr(default) must work sanely."""

    def test_hasattr_true_for_real_subcommand(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        assert hasattr(api, "init")
        assert hasattr(api, "add")

    def test_hasattr_true_for_alias(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        # "setup" is an alias for "init"
        assert hasattr(api, "setup")

    def test_hasattr_false_for_nonexistent(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        assert not hasattr(api, "definitely_not_a_subcommand")
        assert not hasattr(api, "frobnicate")

    def test_getattr_with_default_returns_default(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        sentinel = object()
        assert getattr(api, "nonexistent_sub", sentinel) is sentinel

    def test_attribute_error_message_suggests_call_form(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(AttributeError, match="nonexistent"):
            _ = api.nonexistent

    def test_dir_lists_subcommands(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        entries = dir(api)
        assert "init" in entries
        assert "add" in entries
        # helper methods still visible
        assert "validate" in entries
        assert "command_string" in entries


class TestConfigKwargSafety:
    def test_config_as_non_underscore_kwarg_raises(self):
        from cli_to_py.run_config import RunConfig
        api = from_help_text("grab", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="_config"):
            api("init", config=RunConfig(timeout=5.0))

    def test_underscore_config_must_be_runconfig_instance(self):
        api = from_help_text("grab", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="RunConfig"):
            api("init", _config="not a runconfig")


class TestCommandResultHelpers:
    """text()/lines()/json() live directly on CommandResult now."""

    def test_text_strips_stdout(self):
        from cli_to_py.schema import CommandResult
        assert CommandResult("hello\n", "", 0).text() == "hello"

    def test_lines_splits_stdout(self):
        from cli_to_py.schema import CommandResult
        assert CommandResult("a\nb\nc\n", "", 0).lines() == ["a", "b", "c"]

    def test_lines_empty_for_blank(self):
        from cli_to_py.schema import CommandResult
        assert CommandResult("  \n  ", "", 0).lines() == []

    def test_json_parses_stdout(self):
        from cli_to_py.schema import CommandResult
        assert CommandResult('{"a": 1}', "", 0).json() == {"a": 1}

    def test_ok(self):
        from cli_to_py.schema import CommandResult
        assert CommandResult("", "", 0).ok() is True
        assert CommandResult("", "", 1).ok() is False
