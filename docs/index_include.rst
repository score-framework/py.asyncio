.. module:: score.asyncio
.. role:: confkey
.. role:: confdefault

*************
score.asyncio
*************

A helper module that allows configuring an :mod:`asyncio` event loop.

Quickstart
==========

If you have no preferences about the library to use, initializing the module
with its defaults is sufficient:

.. code-block:: ini

    [score]
    modules =
        score.asyncio

You can then access the loop on the configured module:

.. code-block:: python

    score.asyncio.loop.run_until_complete(coroutine)

API
===

.. autofunction:: init

.. autoclass:: ConfiguredAsyncioModule()

    .. automethod:: await

    .. automethod:: await_multiple
