from score.asyncio import init
import asyncio


def test_stopped_loop():
    task_done = False

    @asyncio.coroutine
    def task():
        nonlocal task_done
        task_done = True

    mod = init({})
    mod.await_(task())
    assert task_done


def test_running_loop():
    task_done = False

    @asyncio.coroutine
    def task():
        nonlocal task_done
        task_done = True

    mod = init({})
    with mod.start_loop():
        mod.await_(task())
        assert task_done
