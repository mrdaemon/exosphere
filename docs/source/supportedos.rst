Supported Remote Platforms
==========================

While Exosphere itself is generally as platform agnostic as possible, it is limited
in what operating systems and platforms it can manage and query.

Platform support for Patches and Updates are implemented via an extensible
provider system, which allows for new platforms to be added in the future.

**If your remote operating system is not supported**, you can still use Exosphere for
the basic SSH ping connectivity checks and Dashboard. They will show up in the
inventory, but no patch and update reporting features will be available for them.

Currently, Exosphere can manage and query the following platforms:

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
  - FreeBSD (all supported versions)
  - *Package Manager*: ``pkg``

.. tip::
   If your preferred platform is not listed, contributions to add new providers 
   are welcome! See the developer documentation for details on implementing new providers.

Common Prerequisites
--------------------

All supported platforms share the same basic requirements, as Exosphere operates
entirely through SSH connections and standard system utilities.

**Essential Requirements**

- **SSH access** to the remote host (with an SSH `agent`_ for authentication)
- **Package manager binaries** installed and available in ``$PATH`` (typically pre-installed)
- **Standard UNIX utilities** such as ``grep``, ``awk``, and ``cut`` (universally available)

**Optional Requirements**

- **Elevated privileges** (sudo) for certain operations on some platforms

**Network Requirements**

- Outbound internet access from managed hosts, at least to the package repositories
- SSH connectivity between your workstation and managed hosts

Some providers may require elevated privileges to perform certain operations, but this is
entirely optional.

More details about all of this are available in the :doc:`connections` section.

.. note::

    Check out the :doc:`Providers Documentation <providers>` for more details on each provider,
    including the exact commands that are run.

.. _agent: https://en.wikipedia.org/wiki/Ssh-agent