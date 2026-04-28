"""Cache integration: convert() with use_cache=True uses the cache on second call."""

import shutil
import time

import pytest

from cli_to_py import convert, convert_sync
from cli_to_py.cache import cache_dir, clear_cache, load_cached_schema
from cli_to_py.constants import CACHE_DIR_ENV


def _missing(bin: str) -> bool:
    return shutil.which(bin) is None


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path))
    yield tmp_path


@pytest.mark.skipif(_missing("git"), reason="git not installed")
class TestCacheRoundtrip:
    async def test_cache_miss_then_hit(self, temp_cache):
        # First call populates cache (scope = subcommands=False)
        api1 = await convert("git", subcommands=False, use_cache=True)
        cached = load_cached_schema("git", subcommands=False)
        assert cached is not None

        # Second call should hit cache and return the same schema
        api2 = await convert("git", subcommands=False, use_cache=True)
        assert api2.binary_name == api1.binary_name
        assert len(api2.schema.command.flags) == len(api1.schema.command.flags)

    async def test_cache_speedup_for_full_enrichment(self, temp_cache):
        # Cold call — full enrichment of git subcommands
        t0 = time.perf_counter()
        api_cold = await convert("git", subcommands=True, use_cache=True)
        cold_time = time.perf_counter() - t0

        # Warm call — should read cache
        t0 = time.perf_counter()
        api_warm = await convert("git", subcommands=True, use_cache=True)
        warm_time = time.perf_counter() - t0

        assert len(api_warm.schema.command.subcommands) == len(api_cold.schema.command.subcommands)
        # Warm must be at least 2x faster than cold (enrichment is ~N spawns)
        assert warm_time < cold_time / 2, f"cold={cold_time:.3f}s warm={warm_time:.3f}s"

    def test_cache_sync(self, temp_cache):
        api1 = convert_sync("git", subcommands=False, use_cache=True)
        assert load_cached_schema("git", subcommands=False) is not None
        api2 = convert_sync("git", subcommands=False, use_cache=True)
        assert api1.binary_name == api2.binary_name

    async def test_cache_scoped_by_subcommands_flag(self, temp_cache):
        """Regression: a schema cached with subcommands=False must NOT be
        served to a call requesting subcommands=True, and vice versa."""
        api_root = await convert("git", subcommands=False, use_cache=True)
        api_full = await convert("git", subcommands=True, use_cache=True)
        # root-only schema has fewer (or zero) enriched subcommands
        root_enriched = sum(1 for s in api_root.schema.command.subcommands if s.flags)
        full_enriched = sum(1 for s in api_full.schema.command.subcommands if s.flags)
        assert full_enriched > root_enriched
