Connections and Security Policies
=================================

This section of the documentation describes the authentication mechanisms (or lack thereof)
provided by Exosphere, as well as how Privileges and Sudo are handled.

Connecting to systems
=====================

Exosphere uses SSH to connect to remote host, using the lovely `Fabric`_ library.
The intended authentication method is to use SSH keys, which should be loaded into your SSH agent.

Exosphere **purposefully does not support password authentication** in any of its subsystems,
to avoid having to deal with the complexities of storing credentials, or prompting from them
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
^^^^^^^^^^^^^^^^

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

.. admonition:: Windows Users

    If you are running Exosphere on Windows, you can enable the `Windows OpenSSH Agent`_
    service that is included with Windows 10 and later, as long as you have the `SSH Client
    feature`_ installed. You can just ``ssh-add`` your keys to the agent, and they will be
    available as expected.

Sudo Policies and Privileges
============================

Exosphere itself tries as much as possible to avoid requiring elevated privileges at all.
Unfortunately, on some platforms, some operations that we rely on do require them.

.. _Fabric: http://www.fabfile.org/
.. _Article on SSH keys: https://wiki.archlinux.org/title/SSH_keys
.. _Windows OpenSSH Agent: https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
.. _SSH Client feature: https://docs.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse