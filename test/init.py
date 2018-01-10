from score.asyncio._init import init, defaults
import asyncio


def test_defaults():
    mod = init({})
    assert mod.backend == 'builtin'
    assert mod.backend == defaults['backend']
    assert mod.use_global_loop == defaults['use_global_loop']
    assert mod.stop_timeout == defaults['stop_timeout']
    if defaults['use_global_loop']:
        assert mod.loop == asyncio.get_event_loop()


def test_default_builtin_loop():
    mod = init({'use_global_loop': 'True'})
    assert mod.backend == 'builtin'
    assert mod.use_global_loop == True
    assert mod.stop_timeout == defaults['stop_timeout']
