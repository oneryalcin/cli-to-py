from cli_to_py.case import kebab_to_snake, snake_to_kebab


def test_snake_to_kebab_basic():
    assert snake_to_kebab("name_only") == "name-only"
    assert snake_to_kebab("set_upstream") == "set-upstream"


def test_snake_to_kebab_noop():
    assert snake_to_kebab("already") == "already"
    assert snake_to_kebab("") == ""


def test_snake_to_kebab_multiple_underscores():
    assert snake_to_kebab("a_b_c_d") == "a-b-c-d"


def test_kebab_to_snake_basic():
    assert kebab_to_snake("dry-run") == "dry_run"
    assert kebab_to_snake("no-color") == "no_color"


def test_roundtrip():
    for word in ["foo", "foo_bar", "foo_bar_baz", "a_b_c"]:
        assert kebab_to_snake(snake_to_kebab(word)) == word
