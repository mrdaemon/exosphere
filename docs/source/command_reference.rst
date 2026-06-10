CLI Command Reference
=====================

Below is a complete reference of all the commands and subcommands available
through the Exosphere CLI. This information is available at runtime via
the ``--help`` option, but is also provided here for reference.

Each command includes detailed descriptions of its purpose, available options,
and usage examples. Commands are organized by functional groups to help you
find what you need quickly.

.. tip::
   You can get help for any specific command by running ``exosphere <command> --help``
   or ``help <command>`` in interactive mode.

inventory
---------

.. cyclopts:: exosphere.commands.inventory:app
   :include-hidden:

.. _command-ref-host:

host
----

.. cyclopts:: exosphere.commands.host:app

connections
-----------

.. cyclopts:: exosphere.commands.connections:app
   :include-hidden:

ui
--

.. cyclopts:: exosphere.commands.ui:app

configuration
-------------

.. cyclopts:: exosphere.commands.config:app

report
------

.. cyclopts:: exosphere.commands.report:app

sudo
----

.. cyclopts:: exosphere.commands.sudo:app

version
-------

.. cyclopts:: exosphere.commands.version:app
