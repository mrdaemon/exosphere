Supported Remote Platforms
==========================

While Exosphere itself is generally as platform agnostic as possible, it is limited
in what operating systems and platforms it can manage and query. This is broadly
limited to Unix-like platforms, including Linux and BSD variants.

There are two tiers of effective support in Exosphere.

1. **Full Support**: Allows connectivity checks, update and patch reporting,
   and detailed host information gathering.

2. **Limited Support**: For unsupported platforms that are still Unix-like,
   Exosphere is limited to basic SSH connectivity checks and presence in
   the dashboard.

Platform support for Patches and Updates is implemented via an extensible
provider system, which allows for new platforms to be added in the future.

**If your remote operating system does not have a provider**, you can still use
Exosphere for the basic SSH ping connectivity checks and Dashboard. They will
show up in the inventory, but no patch and update reporting features will be available,
*as long as it is a Unix-like operating system and obeys basic POSIX standards.*

Unfortunately, this excludes exotic things such as Windows, routers with SSH enabled
but proprietary, non-Unix-like operating systems, etc. Discovery will not work at all
for these systems, and they should probably not be added to the inventory.

Compatibility List
------------------

✅ Exosphere **fully supports** the following platforms:

**Debian-based Systems**
  - Debian (all versions)
  - Ubuntu and derivatives (Mint, Pop!_OS, etc.)
  - *Package Manager*: ``apt`` only

**Red Hat-based Systems**
  - Red Hat Enterprise Linux (RHEL)
  - CentOS / CentOS Stream
  - AlmaLinux / Rocky Linux
  - Fedora
  - *Package Managers*: ``yum`` (RHEL/CentOS 7 and earlier) or ``dnf`` (modern systems)

**BSD Systems**
  - FreeBSD (all supported versions and minor variants)
  - OpenBSD (all supported versions)
  - *Package Managers*: ``pkg`` (FreeBSD), ``pkg_add`` (OpenBSD)

.. admonition:: note

   FreeBSD optionally requires the ``sudo`` package for repository sync operations.
   Unfortunately ``doas`` is not supported at this time.


☑️ Exosphere has **limited support** for the following platforms:

- Other Linux distributions (e.g., Arch Linux, Gentoo, NixOS, etc.)
- Other BSD systems (e.g. NetBSD)
- Other Unix-like systems (e.g., Solaris, AIX, IRIX, Mac OS)

The bar for entry is fairly low to fit this description, as long as it can be connected
to via SSH, has a POSIX shell available [#binsh]_ and returns something useful via
``uname -s``, it will work here.

❌ Exosphere explicitly **does not support** the following platforms:

- Windows (all versions, but WSL over SSH is supported)
- Network Equipment with proprietary operating systems (e.g., Cisco IOS, Juniper JunOS)
- Other non-Unix-like operating systems that support SSH

.. tip::
   If your preferred platform is not supported, contributions to add new providers
   are welcome! See the developer documentation for details on implementing new providers.

Common Prerequisites
--------------------

All supported platforms share the same basic requirements, as Exosphere operates
entirely through SSH connections and standard system utilities.

**Essential Requirements**

- **SSH access** to the remote host (with an SSH `agent`_ for authentication)
- **Package manager binaries** installed and available in ``$PATH`` (typically pre-installed)
- **A POSIX Shell** [#binsh]_ (present on every supported platform)
- **Standard UNIX utilities** such as ``grep``, ``awk``, and ``cut`` (POSIX-compliant, typically available by default)

.. [#binsh]
    Exosphere runs all remote queries through the POSIX standard ``/bin/sh``
    shell, which is present on all supported platforms, ensuring consistent
    behavior across them.


**Optional Requirements**

- **Elevated privileges** for certain operations on some platforms (i.e. `root`)
- ``sudo`` installed on the remote host (if needed) and :doc:`configured properly <sudo>`

See below for more details.

**Network Requirements**

- Outbound internet access from managed hosts, at least to the package repositories
- SSH connectivity between your workstation and managed hosts

Some providers may require elevated privileges to perform certain operations, but this is
entirely optional.

More details about all of this are available in the :doc:`connections` and
:doc:`sudo` sections.

.. note::

    Check out the :doc:`Providers Documentation <providers>` for more details on each provider,
    including the exact commands that are run.

.. _agent: https://en.wikipedia.org/wiki/Ssh-agent
