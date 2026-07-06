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
from tests.fixtures import CLAP_STYLE_HELP, REACT_GRAB_HELP, REACT_GRAB_INIT_HELP


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

    def test_snake_case_attribute_resolves_hyphenated_subcommand(self):
        api = from_help_text(
            "tool",
            "Usage: tool [options]\n\nCommands:\n  do-stuff  do things\n",
        )
        assert hasattr(api, "do_stuff")
        assert api._resolve_alias("do_stuff") == "do-stuff"
        assert api.command_string("do_stuff") == "tool do-stuff"


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


class TestGlobalOptions:
    """`_global` options must render BEFORE the subcommand (issue #7):
    git -C /path log, docker --context x ps — placing them after is
    rejected by the binary."""

    def test_global_renders_before_subcommand(self):
        api = from_help_text("git", REACT_GRAB_HELP)
        cmd = api.command_string("init", _global={"C": "/repo"}, force=True)
        assert cmd == "git -C /repo init --force"

    def test_global_without_subcommand(self):
        api = from_help_text("git", REACT_GRAB_HELP)
        assert api.command_string(_global={"C": "/repo"}) == "git -C /repo"

    def test_global_long_flag_and_value(self):
        api = from_help_text("docker", REACT_GRAB_HELP)
        cmd = api.command_string("init", _global={"context": "prod"})
        assert cmd == "docker --context prod init"

    def test_sync_api_global_renders_before_subcommand(self):
        api = from_help_text_sync("git", REACT_GRAB_HELP)
        cmd = api.command_string("init", _global={"C": "/repo"})
        assert cmd == "git -C /repo init"

    def test_global_must_be_dict(self):
        api = from_help_text("git", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="_global"):
            api.command_string("init", _global=["-C", "/repo"])

    def test_global_rejects_positionals(self):
        api = from_help_text("git", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="positionals"):
            api.command_string("init", _global={"_": ["x"]})

    def test_global_uses_root_equals_policy(self):
        # A subcommand may define a same-named flag with equals form; the
        # global bucket must keep the ROOT form or the binary rejects it.
        from cli_to_py import parse_help_text
        api = from_help_text(
            "tool",
            "Usage: tool [options]\n\nOptions:\n  --log-level <level>  level\n\n"
            "Commands:\n  run  run it\n",
        )
        sub_help = "Usage: tool run [options]\n\nOptions:\n  --log-level=<level>  level\n"
        api.schema.command.subcommands[0].flags = (
            parse_help_text("tool", sub_help).command.flags
        )
        cmd = api.command_string("run", _global={"log_level": "info"}, log_level="debug")
        assert cmd == "tool --log-level info run --log-level=debug"

    def test_validate_rejects_non_dict_global_like_call(self):
        # validate() must not approve a shape __call__ raises on.
        api = from_help_text("git", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="_global"):
            api.validate(_global=["-C", "/repo"])

    def test_validate_rejects_positionals_in_global_like_call(self):
        api = from_help_text("git", REACT_GRAB_HELP)
        import pytest
        with pytest.raises(TypeError, match="positionals"):
            api.validate(_global={"_": ["x"]})

    def test_validate_accepts_known_global_flag(self):
        api = from_help_text("uv", CLAP_STYLE_HELP)
        assert api.validate(_global={"verbose": True}) == []

    def test_validate_flags_unknown_global_key(self):
        api = from_help_text("uv", CLAP_STYLE_HELP)
        errors = api.validate(_global={"definitely_not_a_flag": True})
        assert any(
            e.kind == "unknown-flag" and e.name == "definitely_not_a_flag"
            for e in errors
        )

def _nested_echo_api(sync: bool = False):
    """API over `echo` with a hand-attached nested tree: pip -> install|add.

    Using echo as the binary lets dispatch tests observe the exact argv the
    library produced (echo prints its args) without depending on a real
    nested CLI being installed.
    """
    from cli_to_py import parse_help_text
    from cli_to_py.schema import ParsedSubcommand

    root_help = (
        "Usage: echo [options] <command>\n\n"
        "Options:\n  -q, --quiet  quiet\n\n"
        "Commands:\n  pip  package ops\n"
    )
    install_flags = parse_help_text(
        "install",
        "Usage: echo pip install [options]\n\n"
        "Options:\n  --index-url=<url>  idx\n  -U, --upgrade  up\n",
    ).command.flags
    api = (from_help_text_sync if sync else from_help_text)("echo", root_help)
    api.schema.command.subcommands[0].subcommands = [
        ParsedSubcommand(name="install", aliases=["add"], description="", flags=install_flags)
    ]
    return api


class TestNestedDispatch:
    """Issue #3: fluent nested subcommand dispatch — api.pip.install(...)."""

    async def test_dot_chain_dispatches_full_path(self):
        api = _nested_echo_api()
        result = await api.pip.install(upgrade=True, _=["httpx"])
        assert result.text() == "pip install --upgrade httpx"

    async def test_nested_alias_resolves(self):
        api = _nested_echo_api()
        result = await api.pip.add(upgrade=True)
        assert result.text() == "pip install --upgrade"

    async def test_call_accepts_space_separated_path(self):
        api = _nested_echo_api()
        result = await api("pip install", upgrade=True)
        assert result.text() == "pip install --upgrade"

    async def test_intermediate_proxy_is_callable(self):
        api = _nested_echo_api()
        result = await api.pip(quiet=True)
        assert result.text() == "pip --quiet"

    def test_sync_dot_chain(self):
        api = _nested_echo_api(sync=True)
        assert api.pip.install(upgrade=True).text() == "pip install --upgrade"

    def test_command_string_nested_with_alias_and_equals(self):
        # nested-level equals policy applies after the subcommand; _global
        # renders before the whole chain with root policy
        api = _nested_echo_api()
        cmd = api.command_string("pip add", index_url="https://x", _global={"q": True})
        assert cmd == "echo -q pip install --index-url=https://x"

    def test_unknown_path_segments_pass_through(self):
        # undocumented nested subcommands stay dispatchable via the call form
        api = _nested_echo_api()
        assert api.command_string("pip download", quiet=True) == "echo pip download --quiet"

    def test_unknown_nested_attr_raises_with_hint(self):
        api = _nested_echo_api()
        import pytest
        with pytest.raises(AttributeError, match="pip nonexistent"):
            api.pip.nonexistent

    def test_validate_nested_flags_typo(self):
        api = _nested_echo_api()
        errors = api.validate("pip install", upgrde=True)
        assert any(
            e.kind == "unknown-flag" and e.suggestion == "upgrade" for e in errors
        )

    def test_validate_nested_accepts_known_flag(self):
        api = _nested_echo_api()
        assert api.validate("pip install", upgrade=True) == []

    def test_validate_unknown_nested_path_raises(self):
        api = _nested_echo_api()
        import pytest
        with pytest.raises(ValueError, match="pip nope"):
            api.validate("pip nope", x=True)

    def test_proxy_dir_and_hasattr(self):
        api = _nested_echo_api()
        assert "install" in dir(api.pip)
        assert "add" in dir(api.pip)
        assert hasattr(api.pip, "install")
        assert not hasattr(api.pip, "remove")


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
