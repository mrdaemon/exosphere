Supported Remote Platforms
==========================

While Exosphere itself is generally as platform agnostic as possible, it is limited
in what operating systems and platforms it can manage and query.

Platform support for Patches and Updates are implemented via an extensible
provider system, which allows for new platforms to be added in the future.

Currently, Exosphere can manage and query the following platforms:

- Debian/Ubuntu and Derivatives (apt only)
- Red Hat/CentOS/Alma/Rocky and Derivatives (yum/dnf)
- FreeBSD (pkg)

Common Prerequisites
--------------------

In general, there are no hard requirements for supported platforms, as everything
is driven through SSH and the relevant package manager binaries, as well as
standard unix utilities such as `grep` that are expected to be available on every
system.

The common prerequisites for management are:

- SSH access to the remote host
- sudoers privilege for synchronizing package catalogs (optional, and only for some providers)
- Package manager binaries installed and available in the PATH (this should be the case by default)
- Standard unix utilities are often expected, such as `grep` and friends.

.. note::

    Check out the :doc:`Providers Documentation <providers>` for more details on each provider,
    including the exact commands that are run.
