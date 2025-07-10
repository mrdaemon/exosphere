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

Catalog Update *requires* sudo privileges, as it needs to run ``apt-get update`` to
update the package cache from repositofy.

Updates retrieval is done using ``apt-get dist-upgrade`` in simulation mode, 
and does *not* require elevated privleges.

Exact Commands ran on remote hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``apt-get update``
- ``apt-get dist-upgrade -s | grep -e '^Inst'``


Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `apt-get`
- `grep`

RedHat-Likes (Yum/DNF)
----------------------

The RedHat provider is implemented in the `exosphere.providers.redhat` module.

It implements the functionality identically between Yum and DNF, as they share
an interface for the relevant commands. The only distinction is the command name.

Internally, using Yum as a provider wraps Dnf, but with a different command name.

Catalog Update *does not* require sudo provileges, as it runs ``yum/dnf makecache``
as the connection user to retrieve the information.

Updates retrieval is done using ``yum/dnf check-update``, and does *not* require
elevated privileges.

Exact Commands ran on remote systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``yum makecache --refresh`` or ``dnf makecache --refresh``
- ``yum check-update --quiet`` or ``dnf check-update --quiet``
- ``yum check-update --security --quiet`` or ``dnf check-update --security --quiet``
- ``yum list installed --quiet`` or ``dnf list installed --quiet``

Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `yum` or `dnf`

Usage Notes and Issues
^^^^^^^^^^^^^^^^^^^^^^

If you have third party repositories enabled, it may be a good idea to connection
to the system as the user Exosphere is configured to use, and issue a manual
run of the ``yum/dnf makecache --refresh`` command **once**, ahead of time.

If you do not do this, it is likely the command will start prompting to accept
repository keys, which will cause the connection to hang indefinitely.

If you encounter this, simply run ``dnf makecache --refresh`` or ``yum makecache --refresh``
manually before running Exosphere.

FreeBSD (Pkg)
-------------

The FreeBSD provider is implemented in the `exosphere.providers.freebsd` module.
It uses the `pkg` command to manage packages and updates.

Catalog Update *does not* require sudo privileges, as it is a no-op, since `pkg`
does not actually require a separate step, and the repositories are synced
automatically otherwise.

Updates retrieval is done using ``pkg upgrade`` in simulation mode, and *does not*
require elevated privileges.

Exact Commands ran on remote systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``pkg audit -q`` for security updates
- ``pkg upgrade -qn | grep -e '^\\s'``

Command dependencies
^^^^^^^^^^^^^^^^^^^^

- `pkg`
- `grep`