Managing Cache
===============

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

Clearing the Cache
------------------
If you encounter issues or inconsistencies with cache, you can clear it.
It can generally safely just be deleted on disk, and will be recreated on next run.

The cache file can also be manually cleared within exosphere in the :doc:`cli`:

.. code-block:: bash

    $ exosphere inventory clear

The confirmation prompt can be bypassed with the ``-f`` flag.

Upon clearing the cache, you will have to perform a full Discovery and subsequent
Refresh of the entire inventory to repopulate it.

.. _pickle: https://docs.python.org/3/library/pickle.html
.. _lzma: https://docs.python.org/3/library/lzma.html
