"""Exercise the `cli-to-py` CLI entry point."""

import ast
import shutil
import subprocess
import sys

import pytest

from cli_to_py.cli import main as cli_main


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestCliEntry:
    def test_help_exit(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            cli_main(["--help"])
        assert excinfo.value.code == 0

    def test_generate_json_to_stdout(self, capsys):
        exit_code = cli_main(["git", "--no-subcommands", "--json"])
        captured = capsys.readouterr()
        assert exit_code == 0
        import json
        data = json.loads(captured.out)
        assert data["binary_name"] == "git"

    def test_generate_wrapper_to_file(self, tmp_path, capsys):
        output = tmp_path / "git_wrapper.py"
        exit_code = cli_main(["git", "--no-subcommands", "-o", str(output)])
        assert exit_code == 0
        assert output.exists()
        code = output.read_text()
        ast.parse(code)  # must be valid Python
        stub = output.with_suffix(".pyi")
        assert stub.exists()

    def test_generated_wrapper_imports_and_runs(self, tmp_path):
        """The whole point: generate a wrapper, import it, call a function, it works."""
        output = tmp_path / "git_gen.py"
        exit_code = cli_main(["git", "--no-subcommands", "-o", str(output)])
        assert exit_code == 0

        # Import the generated module via importlib
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("git_gen", str(output))
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        # Register in sys.modules so dataclass type resolution can find classes
        sys.modules["git_gen"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            pass

        # Call status — should return a CommandResult
        result = module.run(version=True)
        assert result.exit_code == 0
        assert "git version" in (result.stdout + result.stderr)


class TestClearCache:
    def test_clear_cache_noop_when_empty(self, tmp_path, monkeypatch, capsys):
        from cli_to_py.constants import CACHE_DIR_ENV
        monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path))
        exit_code = cli_main(["--clear-cache"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Cleared" in captured.out


class TestBinaryNotFound:
    def test_missing_binary_exits_nonzero(self, capsys):
        exit_code = cli_main(["definitely-not-a-real-binary-xyz"])
        assert exit_code != 0
