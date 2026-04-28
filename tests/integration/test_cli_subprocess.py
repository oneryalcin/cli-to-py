"""Black-box test of the cli-to-py CLI, invoked as a real subprocess.

This is the most realistic check: build a wheel, install it into an isolated
venv via `uv run --with`, and invoke `cli-to-py` the way a user would.
"""

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


def _run_cli_module(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the CLI as `python -m cli_to_py.cli ...` from the repo checkout.

    We use this rather than the `cli-to-py` script entry point so the test
    doesn't require a pip-install step — it uses the source directly.
    """
    return subprocess.run(
        [sys.executable, "-m", "cli_to_py.cli", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
    )


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestSubprocessCli:
    def test_help_shows_usage(self):
        result = _run_cli_module("--help")
        assert result.returncode == 0
        assert "Usage" in result.stdout or "usage" in result.stdout

    def test_json_output(self):
        result = _run_cli_module("git", "--no-subcommands", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["binary_name"] == "git"

    def test_wrapper_output_parses_as_python(self):
        result = _run_cli_module("git", "--no-subcommands")
        assert result.returncode == 0
        ast.parse(result.stdout)

    def test_stub_flag_produces_stub(self):
        result = _run_cli_module("git", "--no-subcommands", "--stub")
        assert result.returncode == 0
        ast.parse(result.stdout)
        assert "class CommandResult" in result.stdout

    def test_output_to_file(self, tmp_path):
        out = tmp_path / "wrapper.py"
        result = _run_cli_module("git", "--no-subcommands", "-o", str(out))
        assert result.returncode == 0
        assert out.exists()
        stub = out.with_suffix(".pyi")
        assert stub.exists()
        # Both are valid Python
        ast.parse(out.read_text())
        ast.parse(stub.read_text())

    def test_missing_binary_returns_nonzero(self):
        result = _run_cli_module("this-binary-does-not-exist-12345")
        assert result.returncode != 0
        assert "not found" in result.stderr or "failed" in result.stderr


class TestWheelInstallE2E:
    """Build the wheel, install it in an isolated env, run the CLI as a user would."""

    @pytest.fixture(scope="class")
    def wheel_path(self, tmp_path_factory):
        build_dir = tmp_path_factory.mktemp("build")
        result = subprocess.run(
            ["uv", "build", "--out-dir", str(build_dir)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"uv build failed: {result.stderr}")
        wheels = list(build_dir.glob("*.whl"))
        if not wheels:
            pytest.skip("no wheel produced")
        return wheels[0]

    def test_wheel_install_and_cli_works(self, wheel_path, tmp_path):
        if shutil.which("uv") is None:
            pytest.skip("uv required")
        if shutil.which("git") is None:
            pytest.skip("git required for test")

        output = tmp_path / "git_wrapper.py"
        result = subprocess.run(
            [
                "uv", "run", "--with", str(wheel_path), "--no-project",
                "cli-to-py", "git", "--no-subcommands", "-o", str(output),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert output.exists()
        ast.parse(output.read_text())
