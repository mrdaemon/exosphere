Managing Cache
==============

Exosphere saves the state of all hosts in a cache file, stored on disk.
This allows the software to remember the state of hosts and updates between runs.
It is `lzma`_ compressed and stored in a binary, `pickle`_ format.

The cache file location can be configured with the relevant option in
:ref:`the configuration<cache_file_option>`.

The default path for the cache file varies by platform and configuration,
but can be displayed with the command:

.. code-block:: exosphere

    exosphere> config paths

Changing options, either globally or per host in the configuration should not be
negatively affected by the cache file, which will update itself accordingly.
If it does not, this is a bug and should be reported.

.. tip::
    Efforts are made with every major release to ensure that cache files from
    previous versions of Exosphere remain compatible and transparently
    upgrade on load. However, if you encounter issues, consider clearing
    the cache as described below.

.. _cache_locking:

Cache Locking & Concurrent Instances
------------------------------------

Since **3.0** Exosphere actively guards against multiple instances trying to
interact with the same cache file, and uses locks to achieve this.

The lock file is placed next to the cache file itself (with the ``.lock``
extension appended), so that the cache file itself is never held open.

The lock is released when the process exits.

If a second instance is started against the same cache, it will refuse to start
with a message along these lines:

.. code-block:: text

    FATAL: Another Exosphere instance is using this cache:
      /home/alice/.local/state/exosphere/exosphere.db
    Ensure no other instances with this configuration are running.

This worked in previous versions, but was never a supported configuration.
Two instances sharing a cache would inevitably overwrite each other, and the
cache is never reloaded at runtime, leading to sub-optimal outcomes.

.. tip::

    If you genuinely need to run two instances side by side (for example, against
    two separate inventories), give each one its own configuration with a distinct
    :option:`cache_file`. They will then take separate locks and each will be
    able to coexist peacefully.

Clearing the Cache
------------------
If you encounter issues or inconsistencies with the cache, you can clear it.
It can generally safely just be deleted on disk, and will be recreated on next run.

The cache file can also be manually cleared within Exosphere in the :doc:`cli`:

.. code-block:: bash

    $ exosphere inventory clear

The confirmation prompt can be bypassed with the ``-f`` flag.

Upon clearing the cache, you will have to perform a full Discovery and subsequent
Refresh of the entire inventory to repopulate it.

.. _pickle: https://docs.python.org/3/library/pickle.html
.. _lzma: https://docs.python.org/3/library/lzma.html
