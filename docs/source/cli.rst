Command Line Interface (CLI)
============================

The primary mode of interaction with Exosphere is through its rich command line interface (CLI).
The CLI is designed to be reasonably intuitive, but also discoverable, allowing
users to explore available commands and options interactively.

Basic Usage
------------

The CLI itself has two main modes of operation:

Normal Mode
   This is the default mode where you can run exosphere commands directly as
   arguments to the `exosphere` command.

Interactive Mode
   You can enter an interactive shell by running ``exosphere`` without any arguments.
   In this mode, the prompt will change to ``exosphere>`` and you can run commands
   interactively. Exosphere will function like a REPL or Shell. You can exit with
   ``exit`` or ``quit``.

.. tip::
   All commands can be run in either mode, but interactive mode is particularly useful for
   exploring commands as well as toggling back and forth between the :doc:`ui` and the CLI.

Getting help
------------

You can explore the root commands available by running ``exosphere --help`` or typing ``help``
in the interactive shell. This will show you a list of available commands and their descriptions.

.. exosphere-help:: exosphere.cli:app
   :title: exosphere --help
   :width: 80

For a complete list of commands and options, see the :doc:`command_reference` page.

Initial Inventory Discovery
---------------------------

The first time you run Exosphere after populating your configuration file with
options and hosts, you should perform a Discovery operation.

This operation will connect to each host and attempt to detect what platform,
operating system, flavor, version and package manager it is using.

It will then assign the appropriate provider to that host, which will allow
Exosphere to query and refresh its package update status from here on.

If a host is present in the inventory, but not currently supported by Exosphere,
it will be marked as such, and left available for Online checks. You will not be
able to perform refresh or repo sync operations on them, and display panels will
omit update information for them.

If a host is present in the inventory, not supported by Exosphere and also
fails discovery due to not being a Unix-like operating system, it will return
an explicit error, and should be removed for smooth operation.

For more details, see the :doc:`supportedos` page.

Inventory discovery can be done by running:

.. code-block:: exosphere

   exosphere> inventory discover

Any errors will be printed to the console as well as the log file.

.. tip::

   You can find out where the log file is located on your system by running:

   .. code-block:: exosphere

      exosphere> config paths

   You can find the path under the ``Log:`` section of the output.

Refreshing Update Status
------------------------

Once you have discovered your hosts, you can refresh their update status
by running:

.. code-block:: exosphere

   exosphere> inventory refresh

This will connect to each host in parallel, and fetch what updates are
available, categorizing them, and storing the metadata in the cache file.

If you want to also synchronize the repositories on each host to ensure
the latest package lists are available, you can run:

.. code-block:: exosphere

   exosphere> inventory refresh --sync

This will run the appropriate package manager command to update the
repositories on each host, before fetching the update status.

.. admonition:: Note

   The ``--sync`` option may require elevated privileges (sudo) on some platforms.
   See the :doc:`connections` page for more details on how to configure this.
   This operation may also take quite a long time, depending on the number of
   hosts and their specifications, as well as the network speed.

You can also do it all at the same time, including discovery, by running:

.. code-block:: exosphere

   exosphere> inventory refresh --discover --sync

Viewing Inventory Status
------------------------

The main command for viewing the status of your inventory is:

.. code-block:: exosphere

   exosphere> inventory status

This will display a table of all hosts, their status and how many updates they have
available.

.. image:: /_static/status_sample.png
   :alt: Example output of `exosphere inventory status`

You can also select one or more specific hosts by providing their names as arguments:

.. code-block:: exosphere

   exosphere> inventory status host1 host2

This will show the status for only those hosts, allowing you to focus on
specific systems.

You can also filter the output to only show hosts with available updates by
using the ``--updates-only`` or ``--security-only`` flags:

.. code-block:: exosphere

   exosphere> inventory status --updates-only
   exosphere> inventory status --security-only

If this results in no hosts matching the criteria, Exosphere will print
a message and exit with **code 3**.

By default, hosts are listed in the order they are defined in the
configuration file. You can sort the table by any column using ``--sort``,
optionally reversing the order with ``--reverse``:

.. code-block:: exosphere

   exosphere> inventory status --sort updates --reverse
   exosphere> inventory status --sort os

The available sort columns are ``host``, ``os``, ``flavor``, ``version``,
``updates``, ``security`` and ``status``.

Sorting and filtering **can be combined freely**.

A useful filter and sort combo you might find useful out of the box would be:

.. code-block:: exosphere

   exosphere> inventory status --updates-only --sort security --reverse

Or, in short form:

.. code-block:: exosphere

   exosphere> inventory status -u -o security -r

It will show hosts with updates, sorted by amount of security updates,
descending, which is a great at-a-glance view of what to patch first.

.. admonition:: Note

   Sorting by ``version`` groups hosts by flavor first, then orders versions
   within each flavor, since version numbers are not directly comparable
   across different flavors (e.g. Debian 12 versus Ubuntu 22.04). Likewise,
   sorting by ``flavor`` groups hosts by OS first, keeping OS families
   together.

   Additionally, hosts with no meaningful data for the selected sort column
   always sort to the bottom of the list, regardless of the requested order.
   Within that bottom tier, Undiscovered hosts sort above Unsupported ones.

You can include additional columns, such as each host's description, with
the ``--full`` flag:

.. code-block:: exosphere

   exosphere> inventory status --full

Viewing Host Details and Updates
--------------------------------

To view detailed information about a specific host, including a detailed
list of available updates, you can run:

.. code-block:: exosphere

   exosphere> host show <hostname>

This will display detailed information about the host, including all of the
useful metadata. This includes the last refresh timestamp, which provider
it is using, etc.

It also will display a table of all available updates.

.. image:: /_static/host_show_sample.png
   :alt: Example output of `exosphere host show`

Security updates are highlighted by default. You can also filter the updates
via ``--security-only`` to only show security updates, or ``--no-updates`` to
refrain from showing the table entirely.

.. tip::

   The ``host`` command is quite versatile and also lets you perform operations
   such as ``refresh`` on a specific host. See the
   :ref:`host commands <command-ref-host>` for more details.

Online Checks
-------------

You can perform a quick online check to see if all your hosts are responding
by running:

.. code-block:: exosphere

   exosphere> inventory ping

This will attempt to SSH into each host and check if it is online. If a host
is not reachable, it will be marked as offline and an error will be printed.

This is **not** an ICMP ping, but rather a full SSH connectivity check.
It will only return "Online" if the host can be connected to successfully,
and a trivial test command can be executed.

It can be a good way of validating connectivity to hosts. If ping returns "Online"
for all hosts, you can be certain your SSH connectivity is working within the
context of Exosphere.

This is by design to avoid scenarios where a host is reachable but not fully
operational, for instance mid-startup or mid-shutdown, which would cause
subsequent queries or operations to fail.

Hosts marked as Offline will be skipped in most operations such as ``refresh``
for performance reasons. You can invoke Ping to refresh this status at any time.

.. image:: /_static/ping_sample.png
   :alt: Example output of `exosphere inventory ping`

Viewing Configuration details
-----------------------------

Exosphere makes it easy to answer questions about where it sourced
its configuration from, what the current active configuration is, and
what has been changed from the defaults.

You can view the path to the configuration file that was loaded by running:

.. code-block:: exosphere

   exosphere> config source

You can view the currently active configuration for Exosphere by running:

.. code-block:: exosphere

   exosphere> config show

If you also wish to see the contents of the inventory, you can supply the
``--full`` option.

You can also show exclusively the configuration options that have been changed:

.. code-block:: exosphere

   exosphere> config diff

The output will include what the default value originally was.

.. _config_edit_cmd:

Editing the configuration file
------------------------------

The ``config`` command has a friendly ``edit`` helper subcommand that allows
you to easily open the configuration file in your preferred text editor, without
needing to consult ``config paths`` or ``config show`` first.

.. code-block:: exosphere

   exosphere> config edit

This launches your editor against the currently loaded configuration file. If no
configuration file exists yet, the default platform path is opened instead, so
you can create one from scratch.

The editor used is determined from the :option:`editor` configuration option.
In its absence, it will fallback to the ``VISUAL`` and ``EDITOR`` environment
variables, and finally a platform default (``notepad`` on Windows, ``vi``
elsewhere).

The command may include arguments: for graphical editors that detach
immediately, pass the appropriate "wait" flag (for example ``code --wait``) so
Exosphere can wait until you are done.

.. note::

   Changes do not affect the running process. They take effect on the next
   start of Exosphere.

After you close the editor, the file is validated. If it is invalid, the error
is shown and you are offered the chance to re-open the editor and fix it. Pass
``--no-validate`` to skip this check.

Viewing the state of SSH connections
------------------------------------

If you have :ref:`SSH Pipelining <ssh_pipelining_docs>` enabled, you can view
the current state of the SSH connection pool by running:

.. code-block:: exosphere

   exosphere> connections show

This will display the currently open SSH connections, their age, and
which hosts they are connected to, as well as tell you when they will be
reaped.

You can manually close them with the following command:

.. code-block:: exosphere

   exosphere> connections close

Both of these commands can take arguments, including specifying particular hosts.
See the built in ``--help`` argument output for details.

If you do not have SSH Pipelining enabled (the default), connections are
automatically closed after each operation, so these commands will have no effect.

Launching the Text-based User Interface
---------------------------------------

You can launch the text-based user interface (TUI) by running:

.. code-block:: exosphere

   exosphere> ui start


This will start the TUI, which provides a more interactive way to view and manage
your inventory. You can navigate through the menus and perform operations using
friendly shortcut keys displayed at the bottom of the screen.

An interesting feature of starting the TUI from the interactive shell like this
is that you can switch back and forth between them seamlessly.

Once you exit the TUI, you will be returned to the ``exosphere>`` prompt,
allowing you to run more targeted or specialized commands.

.. tip::

   An interesting feature of the TUI is that it also gives you easy access to
   logs, and includes a nice built-in scrollable viewer.

For more details on the TUI, continue on to the :doc:`ui` page.

Return Codes
------------

Exosphere uses specific return codes to indicate the outcome of commands.
Key return codes are typically:

- **0**: Success - The command completed successfully without any issues.
- **1**: Input Error - The problem is in what you asked: invalid arguments or
  options, an unknown host name, or a declined confirmation prompt.
- **2**: Application Error - We couldn't do what you asked: an operation failed
  while running, such as a host that could not be reached or refreshed.
- **3**: Special - A condition was met, not necessarily an error.

The special return code (3) is used very deliberately and is intended to
assist with scripting and automation, where you need to differentiate between
errors and specific conditions.

For instance, ``exosphere version check`` will return 3 if updates are available,
and the various ``--updates-only`` filters on ``inventory status`` will also
return 3 if no hosts matched what you requested, and lastly, ``sudo generate``
will return it as well if no sudoers snippet needs to be generated for that
host/provider.

Commands returning 3 will typically inform you of the meaning in their
help text.

.. admonition:: Note

   In versions of Exosphere prior to **3.0**, the "input" and "application" return
   codes were the other way around, with input errors returning 2 and application
   errors returning 1. This was in fact the major breaking change that justified
   the version bump.

Beyond the Basics
-----------------

Every command offers exhaustive built in documentation. Feel free to explore
the available commands and options with the ``--help`` flag, or by running
``help`` in the interactive shell.

For advanced, file based reporting, see the :doc:`reporting` page.

A complete :doc:`command_reference` is also available, which provides
a comprehensive list of all the commands and their options.
