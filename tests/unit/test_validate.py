from cli_to_py import from_help_text_sync
from cli_to_py.parse_help import parse_help_text
from cli_to_py.validate import validate_options
from tests.fixtures import REACT_GRAB_INIT_HELP


class TestUnknownFlag:
    def test_typo_flagged_with_suggestion(self):
        api = from_help_text_sync("grab", REACT_GRAB_INIT_HELP)
        errors = api.validate(yess=True)
        assert len(errors) == 1
        assert errors[0].kind == "unknown-flag"
        assert errors[0].suggestion == "yes"

    def test_valid_flag_accepted(self):
        api = from_help_text_sync("grab", REACT_GRAB_INIT_HELP)
        errors = api.validate(yes=True, force=True)
        assert errors == []

    def test_short_flag_alias_accepted(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options]\n\nOptions:\n  -v, --verbose  enable\n",
        )
        errors = validate_options(schema.command, {"v": True})
        assert errors == []

    def test_completely_unknown_flag_no_suggestion(self):
        api = from_help_text_sync("grab", REACT_GRAB_INIT_HELP)
        errors = api.validate(totally_unrelated_flag=True)
        assert any(e.kind == "unknown-flag" for e in errors)
        # "totally_unrelated_flag" has no close match in the schema


class TestTypeMismatch:
    def test_boolean_flag_given_string(self):
        api = from_help_text_sync("grab", REACT_GRAB_INIT_HELP)
        errors = api.validate(yes="maybe")
        assert any(e.kind == "type-mismatch" for e in errors)

    def test_value_flag_given_bool(self):
        api = from_help_text_sync("grab", REACT_GRAB_INIT_HELP)
        errors = api.validate(key=True)
        assert any(e.kind == "type-mismatch" for e in errors)


class TestPositionals:
    def test_extra_positionals_flagged(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options] <file>\n\nOptions:\n  -v, --verbose  enable\n",
        )
        errors = validate_options(schema.command, {"_": ["a.txt", "b.txt", "c.txt"]})
        assert any(e.kind == "variadic-mismatch" for e in errors)

    def test_missing_required_positional(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options] <file>\n\nOptions:\n  -v, --verbose  enable\n",
        )
        errors = validate_options(schema.command, {"verbose": True})
        assert any(e.kind == "missing-positional" for e in errors)

    def test_variadic_allows_many(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [files...]\n\nOptions:\n  -v, --verbose  enable\n",
        )
        errors = validate_options(schema.command, {"_": ["a", "b", "c", "d"]})
        assert not any(e.kind == "variadic-mismatch" for e in errors)


class TestChoices:
    def test_invalid_choice_flagged(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options]\n\nOptions:\n  --level <level>  one of {low,medium,high}\n",
        )
        errors = validate_options(schema.command, {"level": "extreme"})
        assert any(e.kind == "invalid-choice" for e in errors)

    def test_valid_choice_accepted(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options]\n\nOptions:\n  --level <level>  one of {low,medium,high}\n",
        )
        errors = validate_options(schema.command, {"level": "low"})
        assert errors == []


class TestValidateSubcommand:
    def test_validate_by_subcommand_name(self):
        # Construct an API with one subcommand (simulated enrichment)
        from cli_to_py.schema import ParsedFlag, ParsedSubcommand
        api = from_help_text_sync("foo", "Usage: foo\n")
        api.schema.command.subcommands.append(ParsedSubcommand(
            name="commit",
            aliases=[],
            description="commit changes",
            flags=[ParsedFlag(
                long_name="message", short_name="-m", description="msg",
                takes_value=True, value_name="msg", default_value=None,
                is_negated=False, is_required=False, choices=None,
                uses_equals=False, is_global=False,
            )],
            positional_args=[],
        ))
        errors = api.validate("commit", massage="x")
        assert len(errors) == 1
        assert errors[0].suggestion == "message"

    def test_unknown_subcommand_raises(self):
        api = from_help_text_sync("foo", "Usage: foo\n")
        import pytest
        with pytest.raises(ValueError):
            api.validate("nonexistent", foo=True)


class TestRequiredFlag:
    def test_missing_required_flag(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options]\n\nOptions:\n  --token <t>  auth token (required)\n",
        )
        errors = validate_options(schema.command, {})
        assert any(e.kind == "missing-required-flag" for e in errors)

    def test_required_flag_can_be_satisfied_by_short_alias(self):
        schema = parse_help_text(
            "foo",
            "Usage: foo [options]\n\nOptions:\n  -t, --token <t>  auth token (required)\n",
        )
        errors = validate_options(schema.command, {"t": "secret"})
        assert errors == []
