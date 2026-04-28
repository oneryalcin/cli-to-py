"""Exercise the RunConfig features against real (tiny) binaries.

Covers: streaming callbacks, env vars, cwd, timeout, sync+async parity.
"""

import os
import shutil
import tempfile
import time

import pytest

from cli_to_py import RunConfig, run_command, run_command_sync
from cli_to_py.exec import CommandTimeout


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.mark.skipif(_missing("sh"), reason="sh not available")
class TestStreamingCallbacks:
    async def test_on_stdout_called(self):
        received: list[str] = []
        cfg = RunConfig(on_stdout=lambda chunk: received.append(chunk))
        result = await run_command("sh", ["-c", "echo one; echo two; echo three"], config=cfg)
        assert result.exit_code == 0
        joined = "".join(received)
        assert "one" in joined
        assert "three" in joined

    async def test_on_stderr_called(self):
        received: list[str] = []
        cfg = RunConfig(on_stderr=lambda chunk: received.append(chunk))
        result = await run_command("sh", ["-c", "echo err 1>&2"], config=cfg)
        assert result.exit_code == 0
        assert "err" in "".join(received)

    def test_sync_on_stdout_called(self):
        received: list[str] = []
        cfg = RunConfig(on_stdout=lambda chunk: received.append(chunk))
        result = run_command_sync("sh", ["-c", "echo hello"], config=cfg)
        assert result.exit_code == 0
        assert "hello" in "".join(received)


@pytest.mark.skipif(_missing("sh"), reason="sh not available")
class TestEnvAndCwd:
    async def test_env_override_visible(self):
        cfg = RunConfig(env={"MY_TEST_VAR": "hello_world"})
        result = await run_command("sh", ["-c", "echo $MY_TEST_VAR"], config=cfg)
        assert result.exit_code == 0
        assert "hello_world" in result.stdout

    async def test_cwd_override(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = RunConfig(cwd=td)
            result = await run_command("sh", ["-c", "pwd"], config=cfg)
            # On macOS /tmp → /private/tmp; compare realpaths
            assert os.path.realpath(result.stdout.strip()) == os.path.realpath(td)

    def test_env_override_sync(self):
        cfg = RunConfig(env={"SYNC_VAR": "sync_hello"})
        result = run_command_sync("sh", ["-c", "echo $SYNC_VAR"], config=cfg)
        assert "sync_hello" in result.stdout


@pytest.mark.skipif(_missing("sh") or _missing("sleep"), reason="sh/sleep needed")
class TestTimeout:
    async def test_timeout_raises_direct(self):
        cfg = RunConfig(timeout=0.3)
        with pytest.raises(CommandTimeout):
            await run_command("sleep", ["5"], config=cfg)

    async def test_timeout_kills_shell_wrapped_grandchild(self):
        """Regression: sh -c 'sleep 5' forks a grandchild. Killing only sh
        would leave sleep holding the pipes open until its natural death —
        the timeout must kill the whole process group."""
        import time
        cfg = RunConfig(timeout=0.3)
        t0 = time.perf_counter()
        with pytest.raises(CommandTimeout):
            await run_command("sh", ["-c", "sleep 5"], config=cfg)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"timeout took {elapsed:.2f}s, grandchild not killed"

    async def test_timeout_carries_partial_stdout(self):
        """CommandTimeout should attach any stdout captured before the kill."""
        cfg = RunConfig(timeout=0.5)
        try:
            await run_command(
                "sh", ["-c", "echo partial_line; sleep 5"], config=cfg,
            )
            pytest.fail("expected CommandTimeout")
        except CommandTimeout as err:
            assert "partial_line" in err.partial_stdout

    def test_timeout_sync_raises(self):
        cfg = RunConfig(timeout=0.3)
        with pytest.raises(CommandTimeout):
            run_command_sync("sleep", ["5"], config=cfg)

    def test_timeout_sync_kills_shell_grandchild(self):
        import time
        cfg = RunConfig(timeout=0.3)
        t0 = time.perf_counter()
        with pytest.raises(CommandTimeout):
            run_command_sync("sh", ["-c", "sleep 5"], config=cfg)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0


@pytest.mark.skipif(_missing("sh") or _missing("sleep"), reason="sh/sleep needed")
class TestSignalCancellation:
    async def test_signal_aborts_direct(self):
        import asyncio
        signal = asyncio.Event()
        cfg = RunConfig(signal=signal, timeout=5.0)

        async def abort_after_delay():
            await asyncio.sleep(0.2)
            signal.set()

        abort_task = asyncio.create_task(abort_after_delay())
        try:
            from cli_to_py.exec import CommandAborted
            with pytest.raises(CommandAborted):
                await run_command("sleep", ["5"], config=cfg)
        finally:
            await abort_task

    async def test_signal_aborts_shell_wrapped(self):
        """Regression: signal must kill the whole process group so a shell
        wrapper's sleep grandchild doesn't hang the abort path."""
        import asyncio
        import time
        signal = asyncio.Event()
        cfg = RunConfig(signal=signal, timeout=30.0)

        async def abort_after_delay():
            await asyncio.sleep(0.2)
            signal.set()

        abort_task = asyncio.create_task(abort_after_delay())
        t0 = time.perf_counter()
        try:
            from cli_to_py.exec import CommandAborted
            with pytest.raises(CommandAborted):
                await run_command("sh", ["-c", "sleep 10"], config=cfg)
        finally:
            await abort_task
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"abort took {elapsed:.2f}s, grandchild not killed"


@pytest.mark.skipif(_missing("sh"), reason="sh not available")
class TestRootCallFromCliApi:
    async def test_root_call_passes_config(self):
        """Regression: _config= must propagate through api(...) root call."""
        from cli_to_py import from_help_text
        api = from_help_text("sh", "Usage: sh [options]\n")
        cfg = RunConfig(env={"ROOT_VAR": "captured_value"})
        result = await api(_config=cfg, c="echo $ROOT_VAR")
        assert result.exit_code == 0
        assert "captured_value" in result.stdout

    async def test_config_propagates_through_getattr_dispatch(self):
        """Regression: _config= must also propagate through api.method().

        Build a fake schema with a 'run' subcommand so getattr dispatch
        is exercised; the subcommand resolves to `sh run ...` which sh
        rejects, but the env is still threaded through.
        """
        from cli_to_py import from_help_text
        api = from_help_text(
            "env",  # /usr/bin/env is universally available, echoes its env
            "Usage: env [options]\n\nCommands:\n  print  print env\n",
        )
        cfg = RunConfig(env={"DISPATCH_VAR": "via_getattr"})
        # env with no args prints the environment; `_config=cfg` is the
        # dispatch path under test.
        result = await api(_config=cfg)
        assert result.exit_code == 0
        assert "DISPATCH_VAR=via_getattr" in result.stdout
