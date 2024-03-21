from score.serve import Worker as WorkerBase
import asyncio
import abc
import concurrent.futures
import sys
import threading

try:
    from asyncio import run_coroutine_threadsafe
except ImportError:

    def run_coroutine_threadsafe(coro, loop):
        future = concurrent.futures.Future()

        def done(task_future):
            exception = task_future.exception()
            if exception:
                future.set_exception(exception)
            else:
                future.set_result(task_future.result())

        def queue_task():
            try:
                task_future = getattr(asyncio, 'async')(coro, loop=loop)
                task_future.add_done_callback(done)
            except Exception as exc:
                if future.set_running_or_notify_cancel():
                    future.set_exception(exc)
                raise

        loop.call_soon_threadsafe(queue_task)
        return future


class Worker(WorkerBase):
    """
    A :class:`score.serve.Worker` that makes use of a configured
    :mod:`score.asyncio` module.

    This base class will add a layer of abstraction to eliminate threading.
    Subclasses can override the functions :meth:`_prepare`, :meth:`_start`,
    :meth:`_pause`, :meth:`_stop` and :meth:`_cleanup`. These functions will be
    called inside a running event loop (which can be accessed as ``self.loop``)
    and can be regular functions or :term:`coroutines <coroutine>`.

    Example implementation:

    .. code-block:: python

        class EchoServer(score.asyncio.Worker):

            @asyncio.coroutine
            def _start(self):
                self.server = yield from self.loop.create_server(myserver)

            def _pause(self):
                self.server.close()
    """

    def __init__(self, asyncio):
        self.asyncio = asyncio

    @property
    def loop(self):
        return self.asyncio.loop

    def prepare(self):
        self._loop_token = self.asyncio.start_loop()
        event = threading.Event()
        future = run_coroutine_threadsafe(self.__prepare(), self.asyncio.loop)
        future.add_done_callback(lambda future: event.set())
        event.wait()
        exception = future.exception()
        if exception:
            raise exception

    def start(self):
        event = threading.Event()
        future = run_coroutine_threadsafe(self.__start(), self.asyncio.loop)
        future.add_done_callback(lambda future: event.set())
        event.wait()
        exception = future.exception()
        if exception:
            raise exception

    def pause(self):
        event = threading.Event()
        future = run_coroutine_threadsafe(self.__pause(), self.asyncio.loop)
        future.add_done_callback(lambda future: event.set())
        event.wait()
        exception = future.exception()
        if exception:
            raise exception

    def stop(self):
        event = threading.Event()
        future = run_coroutine_threadsafe(self.__stop(), self.asyncio.loop)
        future.add_done_callback(lambda future: event.set())
        event.wait()
        self._loop_token.release()
        exception = future.exception()
        if exception:
            raise exception

    def cleanup(self):
        try:
            event = threading.Event()
            future = run_coroutine_threadsafe(self.__cleanup(),
                                              self.asyncio.loop)
            future.add_done_callback(lambda future: event.set())
            event.wait()
            exception = future.exception()
            if exception:
                raise exception
        finally:
            self._loop_token.release()

    @abc.abstractmethod
    def _prepare(self):
        """
        Equivalent of :meth:`Worker.prepare`.

        This function will be called inside a running event loop.
        """

    @abc.abstractmethod
    def _start(self):
        """
        Equivalent of :meth:`Worker.start`.

        This function will be called inside a running event loop.
        """

    @abc.abstractmethod
    def _pause(self):
        """
        Equivalent of :meth:`Worker.pause`.

        This function will be called inside a running event loop.
        """

    def _stop(self):
        """
        Equivalent of :meth:`Worker.stop`.

        This function will be called inside a running event loop.
        """

    @abc.abstractmethod
    def _cleanup(self, exception):
        """
        Equivalent of :meth:`Worker.cleanup`.

        This function will be called inside a running event loop.
        """

    if sys.version_info[0] == 3 and sys.version_info[1] < 7:

        @asyncio.coroutine
        def __prepare(self):
            result = self._prepare()
            if asyncio.iscoroutine(result):
                result = yield from result

        @asyncio.coroutine
        def __start(self):
            result = self._start()
            if asyncio.iscoroutine(result):
                result = yield from result

        @asyncio.coroutine
        def __pause(self):
            result = self._pause()
            if asyncio.iscoroutine(result):
                result = yield from result

        @asyncio.coroutine
        def __stop(self):
            result = self._stop()
            if asyncio.iscoroutine(result):
                result = yield from result

        @asyncio.coroutine
        def __cleanup(self, exception):
            result = self._cleanup(exception)
            if asyncio.iscoroutine(result):
                result = yield from result

    else:

        async def __prepare(self):
            result = self._prepare()
            if asyncio.iscoroutine(result):
                result = await result

        async def __start(self):
            result = self._start()
            if asyncio.iscoroutine(result):
                result = await result

        async def __pause(self):
            result = self._pause()
            if asyncio.iscoroutine(result):
                result = await result

        async def __stop(self):
            result = self._stop()
            if asyncio.iscoroutine(result):
                result = await result

        async def __cleanup(self, exception):
            result = self._cleanup(exception)
            if asyncio.iscoroutine(result):
                result = await result
