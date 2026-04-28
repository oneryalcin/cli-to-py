"""Test color auto-detection logic (now in env_utils).

The rule: FORCE_COLOR / CLICOLOR_FORCE should be set in the child env when
- streaming callbacks are present (on_stdout or on_stderr)
- AND the relevant parent stream is attached to a tty
"""

from cli_to_py.env_utils import build_env, should_force_color
from cli_to_py.run_config import RunConfig


def test_no_callbacks_no_force_color(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    cfg = RunConfig()
    assert should_force_color(cfg) is False


def test_callbacks_but_not_tty_no_force_color(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    cfg = RunConfig(on_stdout=lambda s: None)
    assert should_force_color(cfg) is False


def test_stdout_callback_and_stdout_tty_forces_color(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    cfg = RunConfig(on_stdout=lambda s: None)
    assert should_force_color(cfg) is True


def test_stderr_callback_and_stderr_tty_forces_color(monkeypatch):
    """on_stderr+stderr-is-tty should also trigger color forcing."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    cfg = RunConfig(on_stderr=lambda s: None)
    assert should_force_color(cfg) is True


def test_build_env_adds_force_color_when_applicable(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    cfg = RunConfig(on_stdout=lambda s: None)
    env = build_env(cfg)
    assert env is not None
    assert env.get("FORCE_COLOR") == "1"
    assert env.get("CLICOLOR_FORCE") == "1"


def test_build_env_removes_no_color_when_forcing(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    cfg = RunConfig(on_stdout=lambda s: None)
    env = build_env(cfg)
    assert env is not None
    assert "NO_COLOR" not in env


def test_build_env_returns_none_when_no_override(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    cfg = RunConfig()
    assert build_env(cfg) is None


def test_build_env_with_custom_env_merges(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    cfg = RunConfig(env={"MY_VAR": "value"})
    env = build_env(cfg)
    assert env is not None
    assert env["MY_VAR"] == "value"
    assert "PATH" in env
