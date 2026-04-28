from cli_to_py.constants import COMMAND_TIMEOUT_S
from cli_to_py.run_config import RunConfig


def test_defaults_are_none():
    """Fields default to None so merge() can distinguish unset from default-valued."""
    cfg = RunConfig()
    assert cfg.timeout is None
    assert cfg.cwd is None
    assert cfg.env is None
    assert cfg.stdio is None
    assert cfg.on_stdout is None
    assert cfg.on_stderr is None
    assert cfg.signal is None


def test_resolved_timeout_fallback():
    assert RunConfig().resolved_timeout() == COMMAND_TIMEOUT_S
    assert RunConfig(timeout=5.0).resolved_timeout() == 5.0


def test_resolved_stdio_fallback():
    assert RunConfig().resolved_stdio() == "pipe"
    assert RunConfig(stdio="inherit").resolved_stdio() == "inherit"


def test_merge_overrides_cwd():
    base = RunConfig(cwd="/a")
    overlay = RunConfig(cwd="/b")
    merged = base.merge(overlay)
    assert merged.cwd == "/b"


def test_merge_preserves_base_when_overlay_unset():
    base = RunConfig(cwd="/a", timeout=60.0)
    overlay = RunConfig()
    merged = base.merge(overlay)
    assert merged.cwd == "/a"
    assert merged.timeout == 60.0


def test_explicit_overlay_timeout_wins():
    """Regression: RunConfig(timeout=COMMAND_TIMEOUT_S) as overlay must NOT
    be dropped. Previous impl used `other.timeout != COMMAND_TIMEOUT_S` as
    a sentinel check, silently dropping explicit 30.0 overrides."""
    base = RunConfig(timeout=60.0)
    overlay = RunConfig(timeout=COMMAND_TIMEOUT_S)  # explicit
    merged = base.merge(overlay)
    assert merged.timeout == COMMAND_TIMEOUT_S


def test_explicit_overlay_stdio_wins():
    base = RunConfig(stdio="inherit")
    overlay = RunConfig(stdio="pipe")
    merged = base.merge(overlay)
    assert merged.stdio == "pipe"


def test_base_stdio_preserved_when_overlay_unset():
    """Regression: base stdio='inherit' must survive an overlay that only
    sets env. Previous impl unconditionally clobbered with overlay.stdio."""
    base = RunConfig(stdio="inherit")
    overlay = RunConfig(env={"X": "1"})
    merged = base.merge(overlay)
    assert merged.stdio == "inherit"


def test_merge_env_combines():
    base = RunConfig(env={"A": "1", "B": "2"})
    overlay = RunConfig(env={"B": "3", "C": "4"})
    merged = base.merge(overlay)
    assert merged.env == {"A": "1", "B": "3", "C": "4"}


def test_merge_none_returns_self():
    base = RunConfig(cwd="/a")
    merged = base.merge(None)
    assert merged is base


def test_merge_callbacks():
    called = []
    base = RunConfig(on_stdout=lambda s: called.append("base"))
    overlay = RunConfig(on_stdout=lambda s: called.append("overlay"))
    merged = base.merge(overlay)
    merged.on_stdout("x")  # type: ignore[misc]
    assert called == ["overlay"]
