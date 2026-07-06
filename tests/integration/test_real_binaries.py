"""End-to-end: convert and run real binaries (git, uv, python3)."""

import shutil

import pytest

from cli_to_py import convert, convert_sync


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestGitAsync:
    async def test_convert_parses_something(self):
        api = await convert("git", subcommands=False)
        assert api.binary_name == "git"

    async def test_status_short_runs(self):
        api = await convert("git", subcommands=False)
        result = await api.status(short=True)
        assert result.exit_code == 0

    async def test_branch_show_current_text(self):
        api = await convert("git", subcommands=False)
        result = await api.branch(show_current=True)
        assert result.exit_code == 0
        branch = result.text()
        assert isinstance(branch, str)
        if not branch:
            return  # detached HEAD, common in GitHub Actions checkouts
        # The output must be a plausible branch name — alphanumeric + - _ /
        # with no embedded newlines or error noise.
        import re
        assert re.fullmatch(r"[A-Za-z0-9._/\-]+", branch), \
            f"unexpected branch output: {branch!r}"

    async def test_command_string(self):
        api = await convert("git", subcommands=False)
        cmd = api.command_string("commit", message="x", all=True)
        assert "git commit" in cmd
        assert "--message" in cmd
        assert "--all" in cmd


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestGitSync:
    def test_convert_sync(self):
        api = convert_sync("git", subcommands=False)
        assert api.binary_name == "git"

    def test_status_sync(self):
        api = convert_sync("git", subcommands=False)
        result = api.status(short=True)
        assert result.exit_code == 0

    def test_branch_text_sync(self):
        api = convert_sync("git", subcommands=False)
        branch = api.branch(show_current=True).text()
        assert isinstance(branch, str)


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestGitGlobalOptions:
    """Issue #7: `git -C <path> log` — -C must render BEFORE the subcommand.
    Targets a repo the process cwd is NOT in, so the test fails if _global
    ever renders after the subcommand again."""

    async def test_global_c_targets_foreign_repo(self, tmp_path):
        import os

        api = await convert("git", subcommands=False)
        init = await api("init", _=[str(tmp_path)])
        assert init.exit_code == 0

        result = await api("rev-parse", _global={"C": str(tmp_path)}, show_toplevel=True)
        assert result.exit_code == 0, result.stderr
        assert os.path.realpath(result.text()) == os.path.realpath(str(tmp_path))

        # dot dispatch goes through a separate closure — cover it too
        status = await api.status(_global={"C": str(tmp_path)}, short=True)
        assert status.exit_code == 0, status.stderr

    async def test_post_subcommand_placement_still_fails(self, tmp_path):
        # Negative control: the pre-fix call shape must keep failing, proving
        # the positive test above exercises real ordering.
        api = await convert("git", subcommands=False)
        await api("init", _=[str(tmp_path)])
        result = await api("rev-parse", C=str(tmp_path), show_toplevel=True)
        assert result.exit_code != 0

    def test_global_c_sync(self, tmp_path):
        import os

        api = convert_sync("git", subcommands=False)
        assert api("init", _=[str(tmp_path)]).exit_code == 0
        result = api("rev-parse", _global={"C": str(tmp_path)}, show_toplevel=True)
        assert result.exit_code == 0, result.stderr
        assert os.path.realpath(result.text()) == os.path.realpath(str(tmp_path))


@pytest.mark.skipif(_missing("uv"), reason="uv not installed")
class TestUvEnrichment:
    async def test_convert_enriches_subcommands(self):
        api = await convert("uv", subcommands=True)
        names = [s.name for s in api.schema.command.subcommands]
        assert "add" in names
        assert "run" in names
        add = next(s for s in api.schema.command.subcommands if s.name == "add")
        assert add.flags is not None and len(add.flags) > 0

    async def test_typo_validation_on_enriched_subcommand(self):
        api = await convert("uv", subcommands=True)
        errors = api.validate("add", editble=True)
        unknown = [e for e in errors if e.kind == "unknown-flag"]
        assert len(unknown) >= 1
        assert unknown[0].suggestion == "editable"

    async def test_nested_subcommand_enriched_recursively(self):
        """Regression: nested subcommands (uv pip install) must get their
        own flags enriched, not just the top level."""
        api = await convert("uv", subcommands=True)
        pip = next(
            (s for s in api.schema.command.subcommands if s.name == "pip"),
            None,
        )
        assert pip is not None
        assert pip.subcommands, "uv pip should have nested subcommands"
        install = next(
            (s for s in pip.subcommands if s.name == "install"), None
        )
        assert install is not None
        assert install.flags is not None
        assert len(install.flags) > 10, "uv pip install should have many flags"
        long_names = [f.long_name for f in install.flags]
        assert "editable" in long_names  # well-known uv pip install flag


@pytest.mark.skipif(_missing("python3"), reason="python3 not installed")
class TestPythonBinary:
    async def test_convert_python(self):
        api = await convert("python3", subcommands=False)
        assert api.binary_name == "python3"

    async def test_version_call(self):
        api = await convert("python3", subcommands=False)
        result = await api(version=True)
        assert result.exit_code == 0
        combined = result.stdout + result.stderr
        assert "Python" in combined
