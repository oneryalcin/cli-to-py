"""Exercise spawn_command and async line iteration."""

import shutil

import pytest

from cli_to_py import spawn_command


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.mark.skipif(_missing("sh"), reason="sh not available")
class TestSpawnIteration:
    async def test_async_for_yields_lines(self):
        proc = await spawn_command("sh", ["-c", "echo a; echo b; echo c"])
        lines = [line async for line in proc]
        code = await proc.exit_code()
        assert lines == ["a", "b", "c"]
        assert code == 0

    async def test_exit_code_awaitable(self):
        proc = await spawn_command("sh", ["-c", "exit 3"])
        code = await proc.exit_code()
        assert code == 3

    async def test_kill_terminates_process(self):
        proc = await spawn_command("sh", ["-c", "sleep 10"])
        proc.kill()
        code = await proc.exit_code()
        # Killed processes return negative code or 137-ish
        assert code != 0
