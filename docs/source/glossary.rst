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

    - Operating System: The Operating System installed on the host (linux, FreeBSD, etc)
    - Version: The version of the operating system (20.04, 22.04, 8, etc)
    - Flavor: The distribution or flavor (Debian, Ubuntu, RedHat, etc)
    - Package Manager: The package manager in use (apt, dnf, yum, etc)

    This usually only needs to be done once per host, but can be repeated if any details
    change, such as a new OS version or package manager change.

Catalog
    The Catalog is the generic term for the authoritative list of packages on the
    host platform. This generally consists of repostories. For instance, on Debian
    and Ubuntu systems, the catalog refers to the repositories configured in the
    `/etc/apt/sources.list` and friends. On RedHat-likes, it refers to the
    repositories configured in `/etc/yum.repos.d/` and so on.

    Refreshing the catalog is the process of updating the local cache from these
    repositories, so that the next update check will have the latest information.
