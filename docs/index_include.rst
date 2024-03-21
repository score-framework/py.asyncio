.. module:: score.asyncio
.. role:: confkey
.. role:: confdefault

*************
score.asyncio
*************

A module that manages a configured :class:`asyncio.AbstractEventLoop`.

Quickstart
==========

If you have no preferences about the library to use, initializing the module
with its defaults is sufficient:

.. code-block:: ini

    [score]
    modules =
        score.asyncio

You can now start/stop the loop from anywhere by grabbing a :term:`loop token`:

.. code-block:: python

    token = configured_asyncio.start_loop()
    # ... the loop is guaranteed to be running now ...
    token.release()
    # if this was the last token, the loop will stop.
    # otherwise it will keep running until all
    # tokens have been released.


Configuration
=============

.. autofunction:: init


Details
=======

.. _asyncio_start_loop:

Starting the Loop
-----------------

Since the sole purpose of this module is to provide a common
:class:`asyncio.AbstractEventLoop` to different, potentially unrelated SCORE
modules, this module must decide when the loop must be started and when it can
be stopped.

This is why any module using this one must indicate its intention to use the
loop by calling the configured module's :meth:`start_loop
<ConfiguredAsyncioModule.start_loop>` method.

The configured module will make sure that the loop is running after the first
call to its :meth:`start_loop <ConfiguredAsyncioModule.start_loop>` method and
will stop the loop automatically when all :term:`loop tokens <loop token>` have
been released.

The following is an excerp from one of the unit tests that demonstrates this
behavior:

.. code-block:: python

    assert not configured_asyncio.loop.is_running()
    for _ in range(10):
        token = configured_asyncio.start_loop()
        assert configured_asyncio.loop.is_running()
        tokens.append(token)
    for token in tokens:
        assert configured_asyncio.loop.is_running()
        token.release()
    assert not configured_asyncio.loop.is_running()

There are three different, identical ways to stop a running loop:

* Invoking the token's :meth:`release <LoopToken.release>` method,
* passing the token to the configured module's :meth:`release_loop
  <ConfiguredAsyncioModule.release_loop>` method and
* using the token as a :term:`context manager` (i.e. in a `with` statement)

.. code-block:: python

    # method 1
    token = configured_asyncio.start_loop()
    try:
        do_something()
    finally:
        token.release()

    # method 2
    token = configured_asyncio.start_loop()
    try:
        do_something()
    finally:
        configured_asyncio.release_loop(token)

    # method 3
    with configured_asyncio.start_loop():
        do_something()

.. note::

    The call to :meth:`start_loop <ConfiguredAsyncioModule.start_loop>` just
    *starts* the loop, which then runs in a different thread. You must use the
    :class:`asyncio.AbstractEventLoop`'s thread-safe methods to interact with
    the running loop:

    .. code-block:: python

        from asyncio import run_coroutine_threadsafe

        with configured_asyncio.start_loop():
            run_coroutine_threadsafe(some_coroutine, configured_asyncio.loop)

API
===

.. autofunction:: init

.. autoclass:: ConfiguredAsyncioModule()

    .. attribute:: loop

        This is the configured :class:`asyncio.AbstractEventLoop`. You should
        not start this loop using the default
        :meth:`run_forever() <asyncio.AbstractEventLoop.run_forever>` and
        :meth:`run_until_complete()
        <asyncio.AbstractEventLoop.run_until_complete>` methods. Use the
        provided :meth:`start_loop` instead.

        See :ref:`asyncio_start_loop` for details.

    .. automethod:: start_loop

    .. automethod:: release_loop

    .. automethod:: await_

    .. automethod:: await_multiple

.. autoclass:: LoopToken()

    .. automethod:: release

