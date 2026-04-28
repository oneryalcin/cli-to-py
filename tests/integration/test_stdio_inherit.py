"""Exercise stdio="inherit" mode — passes through parent's stdin/stdout/stderr.

In this mode run_command returns empty stdout/stderr (captures nothing);
all output goes directly to the parent process.
"""

import shutil

import pytest

from cli_to_py import RunConfig, run_command, run_command_sync


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.mark.skipif(_missing("true"), reason="true not available")
class TestStdioInherit:
    async def test_inherit_returns_empty_but_succeeds(self, capfd):
        cfg = RunConfig(stdio="inherit")
        result = await run_command("true", [], config=cfg)
        assert result.exit_code == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_inherit_sync(self, capfd):
        cfg = RunConfig(stdio="inherit")
        result = run_command_sync("true", [], config=cfg)
        assert result.exit_code == 0

    async def test_inherit_nonzero_exit(self):
        cfg = RunConfig(stdio="inherit")
        result = await run_command("false", [], config=cfg)
        assert result.exit_code != 0

    async def test_inherit_with_echo_captured_by_capfd(self, capfd):
        # In inherit mode the child's output goes to the parent's stdout,
        # which pytest's capfd captures.
        cfg = RunConfig(stdio="inherit")
        await run_command("sh", ["-c", "echo inherited_output"], config=cfg)
        captured = capfd.readouterr()
        assert "inherited_output" in captured.out
