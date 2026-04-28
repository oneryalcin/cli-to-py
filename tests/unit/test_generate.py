import ast

from cli_to_py import parse_help_text
from cli_to_py.generate import generate_json, generate_stub, generate_wrapper
from tests.fixtures import REACT_GRAB_HELP, REACT_GRAB_INIT_HELP


def test_wrapper_is_valid_python():
    schema = parse_help_text("grab", REACT_GRAB_HELP)
    code = generate_wrapper(schema)
    ast.parse(code)


def test_wrapper_defines_subcommand_functions():
    schema = parse_help_text("grab", REACT_GRAB_HELP)
    code = generate_wrapper(schema)
    assert "def init(" in code
    assert "def add(" in code
    assert "def remove(" in code


def test_wrapper_embeds_binary_name():
    schema = parse_help_text("grab", REACT_GRAB_HELP)
    code = generate_wrapper(schema)
    assert "BINARY: str = 'grab'" in code


def test_wrapper_includes_runtime_helper():
    schema = parse_help_text("grab", REACT_GRAB_HELP)
    code = generate_wrapper(schema)
    assert "_to_args" in code
    assert "_run_sync" in code
    assert "_run_async" in code


def test_stub_is_valid_python():
    schema = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    stub = generate_stub(schema)
    ast.parse(stub)


def test_stub_has_command_result_class():
    schema = parse_help_text("grab", REACT_GRAB_INIT_HELP)
    stub = generate_stub(schema)
    assert "class CommandResult" in stub


def test_generate_json_is_valid_json():
    import json
    schema = parse_help_text("grab", REACT_GRAB_HELP)
    dump = generate_json(schema)
    data = json.loads(dump)
    assert data["binary_name"] == "grab"
    assert isinstance(data["command"]["subcommands"], list)


def test_wrapper_handles_hyphenated_names():
    help_text = "Usage: foo [options]\n\nCommands:\n  do-stuff  do things\n"
    schema = parse_help_text("foo", help_text)
    code = generate_wrapper(schema)
    ast.parse(code)
    # "do-stuff" → "do_stuff"
    assert "def do_stuff(" in code
