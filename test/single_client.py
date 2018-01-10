from score.asyncio import init
import time


def test_start_stop():
    mod = init({})
    assert not mod.loop.is_running()
    token = mod.start_loop()
    try:
        assert mod.loop.is_running()
        mod.release_loop(token)
        assert not mod.loop.is_running()
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise


def test_context():
    mod = init({})
    assert not mod.loop.is_running()
    try:
        with mod.start_loop():
            assert mod.loop.is_running()
        assert not mod.loop.is_running()
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise


def test_multiple_starts():
    mod = init({})
    assert not mod.loop.is_running()
    tokens = []
    try:
        for _ in range(10):
            token = mod.start_loop()
            assert mod.loop.is_running()
            tokens.append(token)
        for token in tokens:
            assert mod.loop.is_running()
            token.release()
        assert not mod.loop.is_running()
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise


def test_wait_for_task():
    mod = init({})
    task_done = False

    def task():
        nonlocal task_done
        time.sleep(.25)
        task_done = True

    assert not mod.loop.is_running()
    try:
        with mod.start_loop():
            mod.loop.call_soon_threadsafe(task)
            assert mod.loop.is_running()
        assert task_done
        assert not mod.loop.is_running()
    except:
        mod.loop.call_soon_threadsafe(mod.loop.stop)
        raise
