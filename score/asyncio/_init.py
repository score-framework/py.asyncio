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
    "backend": "default",
    "use_global_loop": False,
}


def init(confdict):
    """
    Initializes this module according to the :ref:`SCORE module initialization
    guidelines <module_initialization>` with the following configuration keys:
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
    elif conf['backend'] == 'default':
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

    def __init__(self, backend, use_global_loop, loop):
        super().__init__("score.asyncio")
        self.backend = backend
        self.use_global_loop = use_global_loop
        self.loop = loop

    def await_multiple(self, coroutines):
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

    def await(self, coroutine):
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
