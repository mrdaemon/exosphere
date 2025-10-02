Glossary and Reference
======================

This section defines common terms and concepts used within Exosphere.

Host
    A host is a remote system that Exosphere connects to in order to gather
    the information it needs. It refers specifically to the remote system
    in the inventory.

Inventory
    The inventory is the collection of Hosts that exosphere knows about.
    It is defined through the configuration file, in the Hosts section.
    Commands and functions that operate on the inventory will generally
    target All Hosts.

Provider
    A Provider is a platform-specific implementation of a package manager
    interface that Exosphere uses to gather information. For instance, on
    Debian and Ubuntu systems, the `apt` provider is used.

    Providers are generally not exposed directly through configuration, just
    automatically detected based on the platform.

Update
    An Update, within exosphere, is an object representing a package that has
    a new version available for installation.

Security
    Whenever the term "Security" is used, it refers to the security status of
    an Update. Security Updates are updates that address security vulnerabilities
    in the software installed on the Host. Exosphere will generally report these
    with some form of emphasis, as they are more urgent than regular updates.

Discovery
    Discovery is the initial process through which Exosphere connects to a host
    and tries to determine platform details. This usually consists of:

    - Operating System: The Operating System installed on the host (Linux, FreeBSD, etc)
    - Version: The version of the operating system (20.04, 22.04, 8, etc)
    - Flavor: The distribution or flavor (Debian, Ubuntu, RedHat, etc)
    - Package Manager: The package manager in use (apt, dnf, yum, etc)

    This usually only needs to be done once per host, but can be repeated if any details
    change, such as a new OS version or package manager change.

Refresh
    A Refresh is the process of querying the host for its current available updates.
    This is generally done by querying the package manager. The process is universally
    read-only, and does not perform any system changes, aside from affecting some
    metadata timestamps and caches on certain platforms and operating systems.

    This is usually separate from a Repository Sync, but often can be combined
    into a single operation depending on context.

Repositories
    The Repositories are the generic term for the authoritative list of packages on the
    host platform. This generally consists of repositories. For instance, on Debian
    and Ubuntu systems, the repositories refer to the remote systems configured in
    `/etc/apt/sources.list` and friends. On RedHat-likes, it refers to the
    repositories configured in `/etc/yum.repos.d/` and so on.

Repository Sync
    Synchronizing the repositories is the process of updating the local host cache
    from these remote servers, so that the next update check will have the latest
    information.

    This is equivalent to running `apt-get update` on Debian-based systems,
    or `dnf makecache` on RedHat-based systems.

    This process is generally safe and read-only, but on systems where
    sudo is required, it may update repository metadata system wide.
    This is generally not an issue, but if it is problematic, rest assured
    that the behavior is entirely opt-in, in these cases.
