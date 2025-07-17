Managing Cache
===============

Exosphere saves the state of all hosts in a cache file, stored on disk.
This allows the software to remember the state of hosts and updates between runs.
It is `lzma`_ compressed and stored in a binary, `pickle`_ format.

The cache file location is determined by the relevant option in :ref:`the configuration<cache_file_option>`.

Changing options, either globally or per host in the configuration should not be
negatively affected by the cache file, which will update itself accordingly.
If it does not, this is a bug and should be reported.

Some effort has been made to ensure the cache file retains compatibility between
exosphere versions, but this is unfortunately difficult to guarantee.

Clearing the Cache
------------------
If you encounter issues or inconsistencies with cache, you can clear it.
It can generally safely just be deleted on disk, and will be recreated on next run.

The cache file can also be manually cleared within exosphere in the :doc:`cli`:

.. code-block:: bash

    $ exosphere inventory clear

The confirmation prompt can be bypassed with the ``-f`` flag.

Upon clearing the cache, you will have to perform a full inventory Discovery
and subsequent Refresh again.

.. _pickle: https://docs.python.org/3/library/pickle.html
.. _lzma: https://docs.python.org/3/library/lzma.html