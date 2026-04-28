from cli_to_py.parse_help import parse_help_text, strip_ansi
from tests.fixtures import CLAP_STYLE_HELP, REACT_DOCTOR_HELP, REACT_GRAB_HELP, REACT_GRAB_INIT_HELP


class TestReactGrabRoot:
    def test_extracts_description(self):
        schema = parse_help_text("grab", REACT_GRAB_HELP)
        assert schema.command.description == "add React Grab to your project"

    def test_extracts_subcommand_names(self):
        schema = parse_help_text("grab", REACT_GRAB_HELP)
        names = [s.name for s in schema.command.subcommands]
        for expected in ["init", "add", "remove", "configure", "upgrade"]:
            assert expected in names

    def test_captures_aliases(self):
        schema = parse_help_text("grab", REACT_GRAB_HELP)
        init = next(s for s in schema.command.subcommands if s.name == "init")
        assert init.aliases == ["setup"]
        add = next(s for s in schema.command.subcommands if s.name == "add")
        assert add.aliases == ["install"]

    def test_skips_help_subcommand(self):
        schema = parse_help_text("grab", REACT_GRAB_HELP)
        names = [s.name for s in schema.command.subcommands]
        assert "help" not in names

    def test_skips_help_and_version_flags(self):
        schema = parse_help_text("grab", REACT_GRAB_HELP)
        long_names = [f.long_name for f in schema.command.flags]
        assert "help" not in long_names
        assert "version" not in long_names


class TestReactGrabInit:
    def test_parses_flags_with_short_and_long(self):
        schema = parse_help_text("init", REACT_GRAB_INIT_HELP)
        yes = next(f for f in schema.command.flags if f.long_name == "yes")
        assert yes.short_name == "-y"
        assert yes.takes_value is False

    def test_flag_with_value(self):
        schema = parse_help_text("init", REACT_GRAB_INIT_HELP)
        key = next(f for f in schema.command.flags if f.long_name == "key")
        assert key.takes_value is True
        assert key.value_name == "key"

    def test_default_value_extraction(self):
        schema = parse_help_text("init", REACT_GRAB_INIT_HELP)
        yes = next(f for f in schema.command.flags if f.long_name == "yes")
        assert yes.default_value == "false"

    def test_long_only_flag(self):
        schema = parse_help_text("init", REACT_GRAB_INIT_HELP)
        skip = next(f for f in schema.command.flags if f.long_name == "skip-install")
        assert skip.short_name is None


class TestReactDoctor:
    def test_wrapped_description_merged(self):
        schema = parse_help_text("react-doctor", REACT_DOCTOR_HELP)
        offline = next(f for f in schema.command.flags if f.long_name == "offline")
        # The description spans two lines; continuation should merge it
        assert "telemetry" in offline.description
        assert "calculate score" in offline.description

    def test_default_on_wrapped_line(self):
        schema = parse_help_text("react-doctor", REACT_DOCTOR_HELP)
        fail_on = next(f for f in schema.command.flags if f.long_name == "fail-on")
        assert fail_on.default_value == "none"

    def test_negated_flag_detected(self):
        schema = parse_help_text("react-doctor", REACT_DOCTOR_HELP)
        no_lint = next((f for f in schema.command.flags if f.long_name == "no-lint"), None)
        assert no_lint is not None
        assert no_lint.is_negated is True

    def test_positional_arg_from_usage(self):
        schema = parse_help_text("react-doctor", REACT_DOCTOR_HELP)
        assert len(schema.command.positional_args) == 1
        assert schema.command.positional_args[0].name == "directory"
        assert schema.command.positional_args[0].required is False

    def test_option_value_placeholders_are_not_positionals(self):
        schema = parse_help_text(
            "tool",
            "Usage: tool [--output <file>] [--config=<path>] <input> [dest]\n\n"
            "Options:\n"
            "  --output <file>  output file\n"
            "  --config=<path>  config path\n",
        )
        assert [(p.name, p.required) for p in schema.command.positional_args] == [
            ("input", True),
            ("dest", False),
        ]


class TestClapStyle:
    def test_parses_clap_style_sections(self):
        schema = parse_help_text("uv", CLAP_STYLE_HELP)
        # Should find both "Cache options:" and "Global options:" flags
        long_names = [f.long_name for f in schema.command.flags]
        assert "no-cache" in long_names
        assert "cache-dir" in long_names
        assert "color" in long_names

    def test_global_option_marked_global(self):
        schema = parse_help_text("uv", CLAP_STYLE_HELP)
        verbose = next(f for f in schema.command.flags if f.long_name == "verbose")
        assert verbose.is_global is True

    def test_choices_extracted_from_description(self):
        schema = parse_help_text("uv", CLAP_STYLE_HELP)
        color = next(f for f in schema.command.flags if f.long_name == "color")
        assert color.choices is not None
        assert "auto" in color.choices
        assert "always" in color.choices
        assert "never" in color.choices

    def test_subcommands_from_clap_style(self):
        schema = parse_help_text("uv", CLAP_STYLE_HELP)
        names = [s.name for s in schema.command.subcommands]
        assert "auth" in names
        assert "add" in names


class TestAnsiStripping:
    def test_strip_ansi_removes_codes(self):
        text = "\x1b[1mBold\x1b[0m plain"
        assert strip_ansi(text) == "Bold plain"

    def test_parse_handles_ansi(self):
        ansi_help = "\x1b[1mUsage:\x1b[0m foo\n\n\x1b[1mOptions:\x1b[0m\n  -v, --verbose  enable verbose mode\n"
        schema = parse_help_text("foo", ansi_help)
        verbose = next((f for f in schema.command.flags if f.long_name == "verbose"), None)
        assert verbose is not None


class TestSectionHeaderVariants:
    def test_hyphenated_header(self):
        text = "Usage: foo\n\nSub-commands:\n  build  build it\n"
        schema = parse_help_text("foo", text)
        names = [s.name for s in schema.command.subcommands]
        assert "build" in names

    def test_header_with_parenthesized_detail(self):
        text = "Usage: foo\n\nIO (v2):\n  -v, --verbose  enable\n"
        schema = parse_help_text("foo", text)
        assert any(f.long_name == "verbose" for f in schema.command.flags)

    def test_header_with_digits(self):
        text = "Usage: foo\n\nOptions2:\n  --x  description\n"
        schema = parse_help_text("foo", text)
        assert any(f.long_name == "x" for f in schema.command.flags)


class TestFlagParserEdgeCases:
    def test_optional_value_bracketed(self):
        """--flag[=VALUE] should still be marked as takes_value."""
        text = "Usage: foo\n\nOptions:\n  --color[=WHEN]    colorize output\n"
        schema = parse_help_text("foo", text)
        color = next((f for f in schema.command.flags if f.long_name == "color"), None)
        assert color is not None
        assert color.takes_value is True

    def test_short_flag_no_space_value(self):
        """-v<level> style (no space between short flag and value placeholder)."""
        text = "Usage: foo\n\nOptions:\n  -v<level>, --verbosity <level>  set verbosity\n"
        schema = parse_help_text("foo", text)
        v = next(
            (f for f in schema.command.flags if f.long_name == "verbosity"), None
        )
        assert v is not None
        assert v.takes_value is True


class TestEmptyInput:
    def test_empty_help_text(self):
        schema = parse_help_text("foo", "")
        assert schema.command.flags == []
        assert schema.command.subcommands == []

    def test_whitespace_only(self):
        schema = parse_help_text("foo", "   \n\n   \n")
        assert schema.command.flags == []
