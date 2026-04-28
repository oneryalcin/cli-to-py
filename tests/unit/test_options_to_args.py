from cli_to_py.options_to_args import options_to_args


class TestBasicConversions:
    def test_bool_true_becomes_long_flag(self):
        assert options_to_args({"verbose": True}) == ["--verbose"]

    def test_bool_false_omitted(self):
        assert options_to_args({"verbose": False}) == []

    def test_string_value_becomes_pair(self):
        assert options_to_args({"output": "file.txt"}) == ["--output", "file.txt"]

    def test_snake_case_becomes_kebab(self):
        assert options_to_args({"dry_run": True}) == ["--dry-run"]

    def test_single_char_becomes_short_flag(self):
        assert options_to_args({"v": True}) == ["-v"]

    def test_single_char_with_value(self):
        assert options_to_args({"f": "file.txt"}) == ["-f", "file.txt"]


class TestArrays:
    def test_list_repeats_flag(self):
        assert options_to_args({"include": ["a", "b"]}) == ["--include", "a", "--include", "b"]

    def test_empty_list_omitted(self):
        assert options_to_args({"include": []}) == []

    def test_tuple_works_like_list(self):
        assert options_to_args({"include": ("a", "b")}) == ["--include", "a", "--include", "b"]


class TestPositionals:
    def test_underscore_list_becomes_positionals(self):
        assert options_to_args({"_": ["file.txt", "other.txt"]}) == ["file.txt", "other.txt"]

    def test_underscore_scalar_wrapped(self):
        assert options_to_args({"_": "file.txt"}) == ["file.txt"]

    def test_positionals_come_after_flags(self):
        args = options_to_args({"verbose": True, "_": ["file.txt"]})
        assert args == ["--verbose", "file.txt"]

    def test_underscore_none_omitted(self):
        assert options_to_args({"_": None}) == []


class TestEqualsFlags:
    def test_equals_form(self):
        assert options_to_args({"msg": "hi"}, equals_flags={"msg"}) == ["--msg=hi"]

    def test_equals_with_list(self):
        assert options_to_args(
            {"msg": ["a", "b"]}, equals_flags={"msg"}
        ) == ["--msg=a", "--msg=b"]


class TestEdgeCases:
    def test_none_value_omitted(self):
        assert options_to_args({"output": None}) == []

    def test_raw_dash_key_passthrough(self):
        assert options_to_args({"-X": "POST"}) == ["-X", "POST"]

    def test_integer_value(self):
        assert options_to_args({"depth": 3}) == ["--depth", "3"]

    def test_empty_dict(self):
        assert options_to_args({}) == []

    def test_none_options_returns_empty(self):
        assert options_to_args(None) == []

    def test_multiple_flags_and_positional(self):
        args = options_to_args({
            "name_only": True,
            "author": "Alice",
            "_": ["HEAD~1"],
        })
        assert args == ["--name-only", "--author", "Alice", "HEAD~1"]
