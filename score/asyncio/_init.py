# Copyright © 2017,2018 STRG.AT GmbH, Vienna, Austria
# Copyright © 2019-2023 Necdet Can Ateşman, Vienna, Austria
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

from score.init import (
    ConfiguredModule, InitializationError, parse_bool, parse_time_interval)
import asyncio
import warnings
import threading
import time


defaults = {
    "backend": "builtin",
    "use_global_loop": False,
    "stop_timeout": None,
}


def init(confdict):
    """
    Initializes this module according to the :ref:`SCORE module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`backend` :confdefault:`"builtin"`
        The library to use for creating the event loop. Current valid values
        are ``uvloop`` and ``builtin``.

    :confkey:`use_global_loop` :confdefault:`False`
        Whether the global loop object should be used. The "global" loop is the
        one returned by :func:`asyncio.get_event_loop()`.

    :confkey:`stop_timeout` :confdefault:`None`
        Defines how long the module will wait for all tasks running in the loop
        to finish when stopping the loop. The value will be interpreted through
        a call to :func:`score.init.parse_time_interval`.

        The default value `None` indicates that the module will wait
        indefinitely. If you want to the loop to terminate immediately, without
        waiting for tasks at all, you must pass "0".

    """
    conf = defaults.copy()
    conf.update(confdict)
    use_global_loop = parse_bool(conf['use_global_loop'])
    stop_timeout = conf['stop_timeout']
    if stop_timeout == 'None':
        stop_timeout = None
    if stop_timeout is not None:
        stop_timeout = parse_time_interval(stop_timeout)
    if conf['backend'] == 'uvloop':
        import uvloop
        if use_global_loop:
            warnings.warn(
                'Ignoring value of "use_global_loop" when using uvloop backend')
        loop = uvloop.new_event_loop()
    elif conf['backend'] == 'builtin':
        if use_global_loop:
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.new_event_loop()
    else:
        import score.asyncio
        raise InitializationError(
            score.asyncio, 'Invalid value for "backend": ' + conf['backend'])
    return ConfiguredAsyncioModule(
        conf['backend'], use_global_loop, stop_timeout, loop)


class ConfiguredAsyncioModule(ConfiguredModule):
    """
    This module's :class:`configuration class <score.init.ConfiguredModule>`.
    """

    def __init__(self, backend, use_global_loop, stop_timeout, loop):
        super().__init__("score.asyncio")
        self.backend = backend
        self.use_global_loop = use_global_loop
        self.stop_timeout = stop_timeout
        self.loop = loop
        self.loop_tokens = []
        self.loop_lock = threading.RLock()

    def __del__(self):
        """
        Stops the loop, if it is still running. Will also :meth:`close()
        <asyncio.AbstractEventLoop.close>` the loop if it is not the global
        event loop.
        """
        if self.loop.is_running():
            event = threading.Event()
            self.loop.call_soon_threadsafe(self.__stop_loop, event)
            event.wait()
        if not self.use_global_loop:
            self.loop.close()

    def await_(self, coroutine):
        """
        Blocks until given *coroutine* is finished and returns the result (or
        raises the exception).

        This method will acquire a :term:`loop token`, schedule the coroutine
        for execution in the configured event loop, await its termination and
        return the result (or raise the exception).

        This is very similar to the builtin method
        :meth:`asyncio.AbstractEventLoop.run_until_complete`, but will work when
        different clients try to execute a coroutine simultanously, regardless
        of the current loop state:

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
        >>> score.asyncio.await_(foo())
        1
        >>> score.asyncio.await_.(bar())
        Traceback (most recent call last):
          File "<console>", line 1, in <module>
          File "/home/can/Projects/score/py.asyncio/score/asyncio/_init.py", line 107, in await_
            return self.loop.run_until_complete(coroutine)
          File "/usr/lib/python3.6/asyncio/base_events.py", line 467, in run_until_complete
            return future.result()
          File "/usr/lib/python3.6/asyncio/coroutines.py", line 210, in coro
            res = func(*args, **kw)
          File "<console>", line 3, in bar
        ZeroDivisionError: division by zero
        """
        with self.start_loop():
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

    def await_multiple(self, coroutines):
        """
        Just like :meth:`await_`, but awaits the completion of multiple
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
                result = self.await_(coroutine)
            except Exception as e:
                results.append((False, e))
            else:
                results.append((True, result))
        return results

    def start_loop(self):
        """
        Makes sure the configured :attr:`loop` is running. Will possibly start
        the loop in a different thread and return a :term:`loop token`.

        This method is thread-safe.

        See :ref:`asyncio_start_loop` for usage details.
        """
        with self.loop_lock:
            token = LoopToken(self)
            self.loop_tokens.append(token)
            if not self.loop.is_running():
                self.loop_thread = threading.Thread(
                    target=self.loop.run_forever)
                self.loop_thread.start()
            return token

    def release_loop(self, token):
        """
        Releases a previously acquired *token*.

        See :ref:`asyncio_start_loop` for usage details.
        """
        with self.loop_lock:
            try:
                self.loop_tokens.remove(token)
            except KeyError:
                return
            token.held = False
            if not self.loop_tokens and self.loop.is_running():
                event = threading.Event()
                self.loop.call_soon_threadsafe(self.__stop_loop, event)
                if not self.loop_tokens:
                    self.loop_thread.join()
                event.wait()

    def __stop_loop(self, event):
        def stop(future=None):
            if not self.loop.is_running() or self.loop_tokens:
                event.set()
                return
            pending_tasks = [t for t in asyncio.Task.all_tasks(self.loop)
                             if not t.done()]
            if not pending_tasks or self.stop_timeout == 0:
                self.loop.stop()
                event.set()
                return
            all_done = asyncio.shield(asyncio.wait(
                pending_tasks, loop=self.loop), loop=self.loop)
            if self.stop_timeout is None:
                wait_task = self.loop.create_task(all_done)
                wait_task.add_done_callback(stop)
            else:
                timeout = self.stop_timeout - (time.time() - stop_time)
                if timeout <= 0:
                    self.loop.stop()
                    event.set()
                wait_task = self.loop.create_task(asyncio.wait_for(
                    all_done, timeout, loop=self.loop))
                wait_task.add_done_callback(stop)
        stop_time = time.time()
        stop()


class LoopToken:
    """
    A :term:`token <loop token>` provided by the configured score.asyncio
    module. The configured asyncio will keep running as long as this token is
    held. Use :meth:`release` to indicate that you're done using the loop.
    """

    def __init__(self, conf):
        self.conf = conf
        self.held = True

    def __del__(self):
        if self.held:
            self.conf.release_loop(self)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.conf.release_loop(self)

    def release(self):
        """
        Releases this token.

        See :ref:`asyncio_start_loop` for details.
        """
        self.conf.release_loop(self)
