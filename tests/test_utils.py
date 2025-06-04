import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import asyncio
import pytest

from utils import async_ttl_cache


# helper function with closure for counting calls
call_counter = {"count": 0}

@async_ttl_cache(seconds=1)
async def sample(value):
    call_counter["count"] += 1
    await asyncio.sleep(0.01)  # simulate async work
    return value + call_counter["count"]


def setup_function(function):
    # clear cache and reset counter before each test
    sample.clear_cache()
    call_counter["count"] = 0


@pytest.mark.asyncio
async def test_cached_result_reused():
    first = await sample(10)
    second = await sample(10)
    assert first == second
    assert call_counter["count"] == 1


@pytest.mark.asyncio
async def test_result_expires_after_ttl():
    first = await sample(5)
    # wait slightly longer than ttl
    await asyncio.sleep(1.1)
    second = await sample(5)
    assert call_counter["count"] == 2
    assert second != first
