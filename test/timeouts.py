from score.asyncio import init
import asyncio
import time
import pytest


def test_abandon_task_on_0_timeout():
    mod = init({'stop_timeout': 0})
    assert not mod.loop.is_running()
    task_done = False

    @asyncio.coroutine
    def task():
        nonlocal task_done
        yield from asyncio.sleep(.1, loop=mod.loop)
        task_done = True

    def add_task():
        mod.loop.create_task(task())

    try:
        with mod.start_loop():
            mod.loop.call_soon_threadsafe(add_task)
            assert mod.loop.is_running()
            time.sleep(.05)
        assert not mod.loop.is_running()
        assert not task_done
        time.sleep(.1)
        assert not task_done
        with mod.start_loop():
            assert mod.loop.is_running()
            time.sleep(.1)
        assert not mod.loop.is_running()
        assert task_done
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise


@pytest.mark.timeout(1)
def test_wait_1_second():
    mod = init({'stop_timeout': '1s'})
    assert not mod.loop.is_running()
    task_done = False

    @asyncio.coroutine
    def task():
        nonlocal task_done
        yield from asyncio.sleep(.25, loop=mod.loop)
        task_done = True

    def add_task():
        mod.loop.create_task(task())

    try:
        start_time = time.time()
        with mod.start_loop():
            mod.loop.call_soon_threadsafe(add_task)
            assert mod.loop.is_running()
        assert task_done
        assert not mod.loop.is_running()
        assert time.time() - start_time >= .25
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise
