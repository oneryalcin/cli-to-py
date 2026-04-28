from cli_to_py.script import Script, script


def test_str_joins_with_and():
    s = script("echo a", "echo b")
    assert str(s) == "echo a && echo b"


def test_empty_script():
    s = script()
    assert str(s) == ""


def test_single_step():
    s = script("echo only")
    assert str(s) == "echo only"


def test_addition_concatenates():
    a = script("echo a")
    b = script("echo b")
    combined = a + b
    assert str(combined) == "echo a && echo b"


def test_addition_with_string():
    a = script("echo a")
    combined = a + "echo b"
    assert str(combined) == "echo a && echo b"


def test_run_sync_executes_chain():
    s = script("echo first", "echo second")
    result = s.run_sync()
    assert result.exit_code == 0
    assert "first" in result.stdout
    assert "second" in result.stdout


def test_run_sync_stops_on_failure():
    s = script("false", "echo should-not-run")
    result = s.run_sync()
    assert result.exit_code != 0
    assert "should-not-run" not in result.stdout


async def test_run_async_executes_chain():
    s = script("echo async1", "echo async2")
    result = await s.run()
    assert result.exit_code == 0
    assert "async1" in result.stdout


def test_repr_shows_steps():
    s = script("a", "b")
    assert "Script" in repr(s)
    assert "'a'" in repr(s)
