from score.asyncio import init
import threading
import time


def test_start_release_2threads():
    mod = init({})
    assert not mod.loop.is_running()
    loop_states = []

    def start_loop():
        token = mod.start_loop()
        loop_states.append(mod.loop.is_running())
        mod.release_loop(token)

    thread1 = threading.Thread(target=start_loop)
    thread2 = threading.Thread(target=start_loop)
    assert not mod.loop.is_running()
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
    assert not mod.loop.is_running()
    assert all(loop_states)
    mod.loop.close()


def test_start_wait_release_10threads():
    mod = init({})
    assert not mod.loop.is_running()
    loop_states = []

    def start_loop():
        time.sleep(.1)
        token = mod.start_loop()
        loop_states.append(mod.loop.is_running())
        mod.release_loop(token)

    threads = list(threading.Thread(target=start_loop) for _ in range(10))
    assert not mod.loop.is_running()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not mod.loop.is_running()
    assert all(loop_states)
    mod.loop.close()


def test_global_start_wait_release_10threads():
    mod = init({'use_global_loop': 'True'})
    assert not mod.loop.is_running()
    loop_states = []

    def start_loop():
        time.sleep(.1)
        token = mod.start_loop()
        loop_states.append(mod.loop.is_running())
        mod.release_loop(token)

    threads = list(threading.Thread(target=start_loop) for _ in range(10))
    assert not mod.loop.is_running()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not mod.loop.is_running()
    assert all(loop_states)
