Connections and Privileges
==========================

This section of the documentation describes the authentication mechanisms (or lack thereof)
provided by Exosphere, as well as how Privileges and Sudo are handled.

Connecting to systems
---------------------

Exosphere uses SSH to connect to remote hosts, using the lovely `Fabric`_ library.
The intended authentication method is to use SSH keys, which should be loaded into your SSH agent.

Exosphere **purposefully does not support password authentication** in any of its subsystems,
to avoid having to deal with the complexities of storing credentials, or prompting for them
in a way that does not introduce a security risk.

The main configurable parameters of host connections (at least through Exosphere's interface)
are as follows:

* :ref:`The username <default_username_option>`, which is used to connect to the remote host.
* :ref:`The port <hosts_port_option>`, which defaults to 22, but can be set to any port you like, per host.
* :ref:`The IP or Hostname <hosts_ip_option>`, which is the address of the host to connect to.

.. admonition:: Note

    Exosphere will (through Fabric) absolutely load and honor ssh client configurations
    from ``~/.ssh/config`` or ``/etc/ssh/ssh_config`` if they exist.

    This means you can set up advanced SSH options, such as host aliases, per-host ssh keys
    and even gateways, without relying on Exosphere to provide the functionality you need.

Using SSH Agents
----------------

An SSH agent is a program that loads your SSH keys into memory, usually with your login session
on your workstation or laptop, allowing you to connect to remote hosts without having to
enter your passphrase every time. This is instrumental to many ssh automation tools and
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

.. _Fabric: http://www.fabfile.org/
.. _Article on SSH keys: https://wiki.archlinux.org/title/SSH_keys
.. _Windows OpenSSH Agent: https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
.. _SSH Client feature: https://docs.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse

.. _sudo-policies-and-privileges:

Sudo Policies and Privileges
============================

Exosphere and its provider modules try, as much as possible, to avoid requiring elevated 
privileges at all. Unfortunately, on some platforms, some operations that we rely on
do require them.

The following section describes how to configure the Sudo Policy for Exosphere as well
as optionally grant the required privileges on the remote hosts.

.. admonition:: Note

    These instructions below are entirely optional, and you can absolutely use
    Exosphere without ever setting up sudoers configuration or privileges.
    You will just be limited to the operations that do not require
    elevated privileges, which is the majority of them.

Enumerating Providers and their Privileges
------------------------------------------

The documentation for :doc:`providers` includes details, but you can query this via the
exosphere CLI and its ``sudo`` command. Here is an example below:

.. code-block:: console

    $ exosphere sudo providers
                                    Providers Requirements                               
    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
    ┃ Provider ┃ Platform                       ┃ Sync Repositories ┃ Refresh Updates ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
    │ Apt      │ Debian/Ubuntu Derivatives      │ Requires Sudo     │ No Privileges   │
    │ Pkg      │ FreeBSD                        │ Requires Sudo     │ No Privileges   │
    │ Dnf      │ Fedora/RHEL/CentOS Derivatives │ No Privileges     │ No Privileges   │
    │ Yum      │ RHEL/CentOS 7 and earlier      │ No Privileges     │ No Privileges   │
    └──────────┴────────────────────────────────┴───────────────────┴─────────────────┘

For instance, we can see here that the ``Apt`` and ``Pkg`` providers require sudo privileges
to sync repositories, but does not require any privileges to refresh updates.

.. note::
   The table above shows the privilege requirements for each operation type:
   
   * **Sync Repositories**: Updating package repository metadata (e.g., ``apt-get update``)
   * **Refresh Updates**: Checking for available package updates

Configuring Sudo Policies
-------------------------

The default Sudo Policy for exosphere is `skip`, :ref:`configured globally <default_sudo_policy_option>`.
This means that Exosphere will not attempt to use sudo at all when running provider commands.

This can also be configured per system, by setting the :ref:`sudo policy option <hosts_sudo_policy_option>`
at the host level.

There are currently two valid settings for the Sudo Policy options:

* ``skip``: Do not use sudo at all, skip operations that require it and emit a warning in logs
* ``nopasswd``: Assume sudoers configuration allows running the provider commands without a password

If you want to be able to use Exosphere to run operations that require sudo privileges, you will
need to configure sudoers on the remote host(s) where this applies to allow them to be run without
a password.

.. attention::

    This can potentially expose your system to security risks if not configured properly.
    See the section below for details on how to configure this safely.

Generating a Sudoers configuration
----------------------------------

You can manually configure sudoers with ``NOPASSWD:`` as you wish, so long as it allows
the commands specified in the :doc:`providers` documentation to run.

However, since this can be a combination of tedious, risky and error-prone,
Exosphere provides a helper command that will generate a sudoers snippet for you,
for any host, or specific provider, while also allowing you to specify a username.

To generate a sudoers configuration snippet for the ``Apt`` provider, for instance,
with the username ``bigadmin``, you can run the following command:

.. code-block:: console

    $ exosphere sudo generate --provider apt --user bigadmin
    # Generated for Debian/Ubuntu Derivatives
    Cmnd_Alias EXOSPHERE_CMDS = /usr/bin/apt-get update
    bigadmin ALL=(root) NOPASSWD: EXOSPHERE_CMDS

You can then take this output and drop it in a file on the remote host, such as
``/etc/sudoers.d/exosphere``, and then switch the Sudo Policy to ``nopasswd`` for that host.

.. admonition:: On usernames

    The username parameter is optional. If you do not specify it, the command will
    try to use, in this order:

    1. The username configured for the host, if any (when using ``--host``)
    2. The username configured in the global configuration, if any
    3. The current local username running the exosphere command

You can also use the ``--host`` option to automatically detect the provider
for a host and generate the appropriate sudoers snippet for it.

For more details, see ``exosphere sudo generate --help``.

Security Considerations
^^^^^^^^^^^^^^^^^^^^^^^

The generated sudoers configuration is designed to be as secure as possible:

* **Specific commands only**: Only the exact commands needed by the provider are allowed
* **Absolute paths**: Commands use full absolute paths (e.g., ``/usr/bin/apt-get``)
* **Root user only**: Commands are restricted to run as ``root`` (not ``ALL``)
* **No password required**: Uses ``NOPASSWD:`` to avoid credential storage/prompting
* **Command aliases**: Uses ``Cmnd_Alias`` for better maintainability

This approach is significantly more secure than granting broad sudo access, as it:

* Limits the attack surface to specific commands that are known in advance
* Prevents privilege escalation beyond the intended operations
* Avoids the security risks of password-based authentication

Alternatives
^^^^^^^^^^^^

If your relevant providers only require sudo privileges for repository synchronization,
and you prefer not to use the sudoers configuration, you can still
configure your remote systems to sync those repositories on a schedule.
You will just not be able to use Exosphere to do it on-demand, but the
repository contents should always be reasonably up to date.

On Debian/Ubuntu systems, consider these options:

* The `unattended-upgrades`_ package, which can be configured to automatically 
  run ``apt-get update`` and optionally ``apt-get upgrade`` on a schedule
* The ``apt-config-auto-update`` package for simpler automatic update configuration
* Custom cron jobs with ``apt-get update`` if you prefer manual control

On FreeBSD, you can set up a cron job or periodic task to run
``/usr/sbin/pkg update`` regularly.

For other distributions, similar automated package management tools are available.

How can I check what the effective Sudo Policy is for a given host?
-------------------------------------------------------------------

You can use the ``sudo check`` helper command.

As an example, to check the effective Sudo Policy for a host named ``bigserver``:

.. code-block:: console

    $ exosphere sudo check bigserver
    Sudo Policy for bigserver

     Global Policy:          skip
     Host Policy:            nopasswd (local)
     Package Manager:        apt

     Can Sync Repositories:  Yes
     Can Refresh Updates:    Yes

This will tell you what the effective Sudo Policy is for that host, as well as
where that is configured. For instance, in the example above, you can see the
global policy is ``skip``, but the host policy has been set to ``nopasswd``
locally, in the inventory host options.

The global Sudo Policy can also be displayed via:

.. code-block:: console

    $ exosphere sudo policy
    Global SudoPolicy: skip

.. _unattended-upgrades: https://wiki.debian.org/UnattendedUpgrades