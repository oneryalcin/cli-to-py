from cli_to_py.command_string import to_command_string


def test_basic_binary():
    assert to_command_string("git", [], {}) == "git"


def test_subcommand():
    assert to_command_string("git", ["status"], {}) == "git status"


def test_flag_with_value():
    assert to_command_string("git", ["commit"], {"message": "hello"}) == "git commit --message hello"


def test_escapes_spaces():
    assert to_command_string("git", ["commit"], {"message": "fix typo"}) == "git commit --message 'fix typo'"


def test_escapes_special_shell_chars():
    result = to_command_string("echo", [], {"_": ["$HOME; rm -rf /"]})
    assert "$HOME" in result
    # shlex.quote should wrap in single quotes to neutralize
    assert "'$HOME; rm -rf /'" in result


def test_boolean_flag():
    assert to_command_string("git", ["push"], {"force": True}) == "git push --force"


def test_list_flag():
    assert to_command_string("git", ["log"], {"author": ["alice", "bob"]}) == "git log --author alice --author bob"


def test_positionals():
    # shlex.quote wraps HEAD~1 in quotes because ~ is shell-special
    assert to_command_string("git", ["diff"], {"_": ["HEAD~1"]}) == "git diff 'HEAD~1'"


def test_plain_positional():
    assert to_command_string("cat", [], {"_": ["file.txt"]}) == "cat file.txt"


def test_equals_flag():
    assert to_command_string("foo", [], {"k": "v"}, equals_flags={"k"}) == "foo -k=v"
