# Copyright © 2017 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

from score.init import ConfiguredModule
import asyncio
import warnings
import threading


defaults = {
    "backend": "builtin",
    "use_global_loop": False,
}


def init(confdict):
    """
    Initializes this module according to the :ref:`SCORE module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`backend` :confdefault:`builtin`
        The library to use for creating the event loop. Current valid values
        are ``pyuv``, ``uvloop`` and ``builtin``.

    :confkey:`use_global_loop` :confdefault:`False`
        Whether the global loop object should be used. The "global" loop is the
        one returned by :func:`asyncio.get_event_loop()`.

    """
    conf = defaults.copy()
    conf.update(confdict)
    if conf['backend'] == 'pyuv':
        import pyuv
        if conf['use_global_loop']:
            loop = pyuv.Loop.default_loop()
        else:
            loop = pyuv.Loop()
    elif conf['backend'] == 'uvloop':
        import uvloop
        if conf['use_global_loop']:
            warnings.warn(
                'Ignoring value of "use_global_loop" when using uvloop backend')
        loop = uvloop.new_event_loop()
    elif conf['backend'] == 'builtin':
        if conf['use_global_loop']:
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.new_event_loop()
    else:
        import score.asyncio
        raise InitializationError(
            score.asyncio, 'Invalid value for "backend": ' + conf['backend'])
    return ConfiguredAsyncioModule(
        conf['backend'], conf['use_global_loop'], loop)


class ConfiguredAsyncioModule(ConfiguredModule):
    """
    This module's :class:`configuration class <score.init.ConfiguredModule>`.
    """

    def __init__(self, backend, use_global_loop, loop):
        super().__init__("score.asyncio")
        self.backend = backend
        self.use_global_loop = use_global_loop
        self.loop = loop

    def await(self, coroutine):
        """
        Blocks until given *coroutine* is finished and returns the result (or
        raises the exception).

        The builtin method :meth:`AbstractEventLoop.run_until_complete` is
        usually sufficient to wait for a coroutine to finish. But if you do not
        know, whether the event loop is running or not, you will need a
        different approach. This method can be used in these circumstances. The
        following example will always work, regardless of the current loop
        state:

        >>> import asyncio
        >>> @asyncio.coroutine
        ... def foo():
        ...     return 1
        ...
        >>> @asyncio.coroutine
        ... def bar():
        ...     return 1 / 0
        ...
        >>> foo()
        <generator object foo at 0x7fea86b20e08>
        >>> score.asyncio.await(foo())
        1
        >>> score.asyncio.await(bar())
        Traceback (most recent call last):
          File "<console>", line 1, in <module>
          File "/home/can/Projects/score/py.asyncio/score/asyncio/_init.py", line 107, in await
            return self.loop.run_until_complete(coroutine)
          File "/usr/lib/python3.6/asyncio/base_events.py", line 467, in run_until_complete
            return future.result()
          File "/usr/lib/python3.6/asyncio/coroutines.py", line 210, in coro
            res = func(*args, **kw)
          File "<console>", line 3, in bar
        ZeroDivisionError: division by zero
        """
        if not self.loop.is_running():
            try:
                # only possible with python>=3.5:
                # test if there is another event loop running in this thread.
                from asyncio.events import _get_running_loop
            except ImportError:
                pass
            else:
                # Only one loop can be active per thread. If we are able to
                # detect, that there is no running loop, we can just start the
                # loop inside this thread. Otherwise, we will need to spawn a
                # new thread for running the loop (see _sync_using_thread).
                if not _get_running_loop():
                    return self.loop.run_until_complete(coroutine)
            return self._sync_using_thread(coroutine)
        else:
            return self._sync_in_running_loop(coroutine)

    def await_multiple(self, coroutines):
        """
        Just like :meth:`await`, but awaits the completion of multiple
        *coroutines*. The return value is different though: the method will
        provide a list of 2-tuples, where the first value is a *bool* indicating
        successful execution of the coroutine and the second value is the
        exception itself or the return value.

        Example with two coroutines, the first successfully returning ``1``,
        while the other raising a `ZeroDivisionError`:

        .. code-block:: python

            [
                (True, 1),
                (False, ZeroDivisionError('division by zero',)),
            ]
        """
        results = []
        for coroutine in coroutines:
            # TODO: This code is executing the coroutines sequentially.
            # It should rather run them inside the same loop.
            try:
                result = self.await(coroutine)
            except Exception as e:
                results.append((False, e))
            else:
                results.append((True, result))
        return results

    def _sync_using_thread(self, coroutine):
        result = None
        exception = None

        def run():
            nonlocal exception, result
            try:
                result = self.loop.run_until_complete(coroutine)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=run)
        thread.start()
        thread.join()

        if exception is not None:
            raise exception

        return result

    def _sync_in_running_loop(self, coroutine):
        result = None
        exception = None
        condition = threading.Condition()
        finished = False

        def resolve(future):
            nonlocal exception, result, finished
            exception = future.exception()
            if exception is None:
                result = future.result()
            with condition:
                finished = True
                condition.notify()

        def create_task():
            task = self.loop.create_task(coroutine)
            task.add_done_callback(resolve)

        self.loop.call_soon_threadsafe(create_task)
        with condition:
            condition.wait_for(lambda: finished)

        if exception:
            raise exception
        return result
