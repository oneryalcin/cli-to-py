import asyncio

import pytest

from cli_to_py.command_future import CommandFuture
from cli_to_py.schema import CommandResult


async def _fake_result(stdout: str) -> CommandResult:
    return CommandResult(stdout=stdout, stderr="", exit_code=0)


async def test_plain_await_returns_command_result():
    fut = CommandFuture(_fake_result("hello\n"))
    result = await fut
    assert result.stdout == "hello\n"
    assert result.exit_code == 0


async def test_text_trims_stdout():
    fut = CommandFuture(_fake_result("  hello  \n"))
    assert await fut.text() == "hello"


async def test_lines_splits_stdout():
    fut = CommandFuture(_fake_result("a\nb\nc\n"))
    assert await fut.lines() == ["a", "b", "c"]


async def test_lines_empty_string_returns_empty_list():
    fut = CommandFuture(_fake_result("   \n  "))
    assert await fut.lines() == []


async def test_json_parses_stdout():
    fut = CommandFuture(_fake_result('{"a": 1, "b": 2}'))
    assert await fut.json() == {"a": 1, "b": 2}


async def test_can_await_twice_same_future():
    """Lazy Task caching should make the same future awaitable multiple times."""
    fut = CommandFuture(_fake_result("x\ny\n"))
    first = await fut
    text = await fut.text()
    assert first.stdout == "x\ny\n"
    assert text == "x\ny"


async def test_text_and_lines_on_same_future():
    fut = CommandFuture(_fake_result("one\ntwo\n"))
    text = await fut.text()
    lines = await fut.lines()
    assert text == "one\ntwo"
    assert lines == ["one", "two"]
