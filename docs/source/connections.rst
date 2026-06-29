Connections and Authentication
==============================

This section of the documentation describes the authentication mechanisms (or lack thereof)
provided by Exosphere, as well as how SSH connections are established and reused.

For how privileges and sudo are handled, see :doc:`sudo`.

Connecting to systems
---------------------

Exosphere uses SSH to connect to remote hosts, using the lovely `Fabric`_ library.
The intended authentication method is to use SSH keys, which should be loaded into your **SSH agent**.

Exosphere **purposefully does not support password authentication** in any of its subsystems,
to avoid having to deal with the complexities of storing credentials, or prompting for them
in a way that does not introduce a security risk.

The main configurable parameters of host connections (at least through Exosphere's interface)
are as follows:

* :ref:`The username <default_username_option>`, which is used to connect to the remote host.
* :ref:`The port <hosts_port_option>`, which defaults to 22, but can be set to any port you like, per host.
* :ref:`The IP or Hostname <hosts_ip_option>`, which is the address of the host to connect to.

.. admonition:: Note

    Exosphere will (through Fabric) absolutely load and honor SSH client configurations
    from ``~/.ssh/config`` or ``/etc/ssh/ssh_config`` if they exist.

    This means you can set up advanced SSH options, such as host aliases, per-host SSH keys
    and even gateways, without relying on Exosphere to provide the functionality you need.

Using SSH Agents
----------------

An **SSH agent** is a program that loads your SSH keys into memory, usually with your login session
on your workstation or laptop, allowing you to connect to remote hosts without having to
enter your passphrase every time. This is instrumental to many SSH automation tools and
workflows.

Exosphere relies on the SSH agent to provide the necessary keys for authentication.

The process for setting up an SSH agent and/or generating key pairs for your hosts is
beyond the scope of this documentation, but plenty of guides are available online,
including your distribution's documentation.

A reasonable place to start is the Arch Linux Wiki's `Article on SSH keys`_,
which is generic enough to apply to most if not all distributions.

.. tip::

    If you are running Exosphere on Windows, you can enable the `Windows OpenSSH Agent`_
    service that is included with Windows 10 and later, as long as you have the `SSH Client
    feature`_ installed. You can just ``ssh-add`` your keys to the agent, and they will be
    available as expected.

Testing connectivity
--------------------

You can test your SSH connectivity to a host using ``discover`` as it will display
a nice table of errors for hosts where connectivity fails.

You can do this for the entire inventory with:

.. code-block:: exosphere

    exosphere> inventory discover

Or for a specific host, such as a host named ``bigserver``:

.. code-block:: exosphere

    exosphere> host discover bigserver

Authentication failures will display clearly in the output. The exact cause, however, can
vary, but you should check the following:

* Ensure your SSH agent is running and has the necessary keys loaded.
* Ensure the username and port are correct in :doc:`configuration`
* Ensure the remote host is reachable over the network and that the SSH service is running.
* Ensure the remote host's SSH configuration allows *Public Key Authentication*

For debugging purposes, you can try connecting to the host yourself with verbose output:

.. code-block:: console

    $ ssh -vvv bigserver

This will provide detailed information about the SSH connection process, which can help
pinpoint the exact issue with authentication or connectivity.

.. tip::

    Remember: Exosphere will honor ``~/.ssh/config`` and ``/etc/ssh/ssh_config``.
    The settings in these files **will** be used. Double check your host aliases,
    if any!

.. _Fabric: https://www.fabfile.org/
.. _Article on SSH keys: https://wiki.archlinux.org/title/SSH_keys
.. _Windows OpenSSH Agent: https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
.. _SSH Client feature: https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse

.. _ssh_pipelining_docs:

SSH Pipelining
--------------

By default, Exosphere closes SSH connections to remote hosts after each
operation (with some exceptions for batching purposes). This ensures no resources
are left open on both the local and remote systems.

Exosphere makes a best-effort attempt to batch queries within an operation to
minimize unnecessary connection churn and overhead, but this is scoped
to individual operations (e.g., ``discover``, ``refresh``, ``sync``, etc.).

If you have a reasonably sizeable inventory and/or find that the overhead of
repeatedly opening and closing SSH connections reduces performance, you can
enable SSH Pipelining via the :ref:`ssh pipelining option <ssh_pipelining_option>`.

When this setting is enabled, Exosphere will not close connections after each
operation, but will instead keep them open for reuse.

Connections will be allowed to idle for a configurable amount of time
(default is 5 minutes) before being automatically closed in the background.

This can speed up operations significantly if your workflow involves multiple
operations in sequence on the same set of hosts, at the cost of leaving
connections to remote hosts open for a longer period of time.

.. admonition:: Note

    Be aware that SSH pipelining is mostly useful if you use exosphere in
    interactive mode (the REPL) or with the Text User Interface (TUI),
    as connections are systematically closed on program exit.
    If you use the CLI for one-off commands, the connections
    will be closed at the end of the command execution anyway.

With pipelining enabled, you can view and manage the currently open
connections via:

.. code-block:: exosphere

    exosphere> connections show

as well as:

.. code-block:: exosphere

    exosphere> connections close

See the `connections` command help for more details.

The configurable values for SSH Pipelining include the :ref:`maximum lifetime
of idle connections <ssh_pipelining_lifetime_option>`, as well as the
:ref:`interval at which they are reaped <ssh_pipelining_reap_interval_option>`.
