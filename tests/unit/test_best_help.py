from cli_to_py.best_help import select_help_output


def test_prefers_stdout_when_stderr_empty():
    assert select_help_output("Usage: foo\nOptions:\n  -v", "") == "Usage: foo\nOptions:\n  -v"


def test_prefers_stderr_when_stdout_empty():
    assert select_help_output("", "Usage: foo") == "Usage: foo"


def test_both_empty_returns_empty_string():
    assert select_help_output("", "") == ""
    assert select_help_output("   ", "  ") == ""


def test_prefers_stream_with_help_signals():
    out = "unrelated noise"
    err = "Usage: foo\nOptions:\n  -v"
    assert select_help_output(out, err) == err


def test_higher_signal_count_wins():
    low = "Usage: foo"
    high = "Usage: foo\nOptions:\n  -v, --verbose\nCommands:\n  build"
    assert select_help_output(low, high) == high


def test_falls_back_to_longer_when_tied():
    a = "short"
    b = "somewhat longer text with no help signals"
    assert select_help_output(a, b) == b
