Providers
=========

Exosphere implements platform support for Patch and Update management through an
extensible :doc:`Providers API <api/providers_api>` that allows for new providers
to be more or less transparently implemented.

Current implementation details and notes for the built-in providers are provided
below.

Debian/Ubuntu (Apt)
-------------------

The Debian/Ubuntu provider is implemented in the `exosphere.providers.debian` module.

Repo sync *requires* sudo privileges, as it needs to run ``apt-get update`` to
update the package cache from repository.

By default, given the stock :ref:`Sudo Policy <default_sudo_policy_option>`,
in Exosphere, Repo sync will **not** run for Debian-like hosts, and you will need
to configure sudoers appropriately before changing the Sudo Policy.

Updates retrieval is done using ``apt-get dist-upgrade`` in simulation mode, 
and does *not* require elevated privileges.

.. admonition:: Note

    If you want repo sync without sudo privileges, you can also just
    install the ``apt-config-auto-update`` package, or configure
    `Unattended Upgrades`_ to achieve this on a schedule. 


Exact Commands ran on remote hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``/usr/bin/apt-get update`` **(requires sudo)**
- ``apt-get dist-upgrade -s | grep -e '^Inst'``


Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `apt-get`
- `grep`

.. _Unattended Upgrades: https://wiki.debian.org/UnattendedUpgrades

RedHat-Likes (Yum/DNF)
----------------------

The RedHat provider is implemented in the `exosphere.providers.redhat` module.

It implements the functionality identically between Yum and DNF, as they share
an interface for the relevant commands. The only distinction is the command name.

Internally, using Yum as a provider wraps Dnf, but with a different command name.

Repo sync *does not* require sudo privileges, as it runs ``yum/dnf makecache``
as the connection user to retrieve the information.

Updates retrieval is done using ``yum/dnf check-update``, and does *not* require
elevated privileges.

Exact Commands ran on remote systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

   If your system uses ``yum`` you can replace ``dnf`` with it here.

- ``dnf --quiet -y makecache --refresh``
- ``dnf --quiet -y check-update``
- ``dnf --quiet -y check-update --security``
- ``dnf --quiet -y list installed <package_name>``
- ``dnf --quiet -y repoquery kernel --latest-limit=1 --queryformat='%{name}.%{arch}  %{version}-%{release}  %{repoid}\n'``

Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `yum` or `dnf`

Usage Notes and Issues
^^^^^^^^^^^^^^^^^^^^^^

In some scenarios, the `yum` or `dnf` commands may hang when running due to
unexpectedly prompting for user input interactively, which Exosphere cannot handle.

The provider is written to avoid this, but if you do encounter this, simply run 
``dnf makecache --refresh`` or ``yum makecache --refresh`` manually on the remote system
and answer any prompts that may appear.

Once that is done, you should be able to run Exosphere commands without issues.

Note that we consider having to do this a bug, and would appreciate if you could
`file a bug report`_.

FreeBSD (Pkg)
-------------

The FreeBSD provider is implemented in the `exosphere.providers.freebsd` module.
It uses the `pkg` command to manage packages and updates.

Repo sync *requires* sudo privileges, as it needs to run ``/usr/sbin/pkg update``
to update the package cache from repository.

This also means you will need to have the ``sudo`` package installed on the
remote system if you want to use this functionality. Unfortunately, ``doas``
is not supported at this time.

By default, given the stock :ref:`Sudo Policy <default_sudo_policy_option>`,
in Exosphere, Repo sync will **not** run for FreeBSD hosts, and you will need
to configure sudoers appropriately before changing the Sudo Policy.

Alternatively, you can run ``/usr/sbin/pkg update`` via a cronjob or similar
mechanism to keep the repository information up to date without having
to configure sudo privileges for Exosphere.

Updates retrieval is done using ``pkg upgrade`` in simulation mode, and *does not*
require elevated privileges.

Exact Commands ran on remote systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``/usr/sbin/pkg update -q`` **(requires sudo)**
- ``pkg audit -q`` for security updates
- ``pkg upgrade -qn | grep -e '^\\s'``

Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `pkg`
- `grep`

.. _file a bug report: https://github.com/mrdaemon/exosphere/issues