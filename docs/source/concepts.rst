How Exosphere Works
===================

Exosphere runs entirely from your own machine. There is no agent to install,
no server to keep running, and nothing extra living on the remote hosts ---
everything happens over plain SSH, driven by the :doc:`cli` or :doc:`ui` on
your workstation or laptop.

This page offers a quick overview of how the pieces fit together, so the
commands in the :doc:`quickstart` (and everywhere else) make sense.

Overview
--------

.. only:: not latex

   .. figure:: _static/concepts-overview.svg
      :alt: Exosphere on your machine fanning out to each host over SSH
      :align: center

      Everything runs from your machine.

Your machine connects to each host over SSH, runs a handful of ordinary, mostly
read-only commands (the kind you could type yourself), and brings the results
back home. The hosts need nothing installed beyond what they already ship
with: an SSH server and a POSIX shell.

See :doc:`supportedos` for the specifics of what is required on each end,
as well as the :doc:`connections` page for details on SSH access.

Concepts
--------

Three concepts carry most of the weight:

**Host**
    One remote system Exosphere connects to.

**Inventory**
    The full collection of hosts, which are defined in your :doc:`configuration <configuration>`.
    Most commands operate on the whole inventory unless you name specific hosts.

**Provider**
    The platform-specific adapter (``apt``, ``dnf``/``yum``, ``pkg``,
    ``pkg_add``) that knows how to ask a given host about its updates. The
    right one is detected automatically during discovery --- you never pick one
    by hand.

The full vocabulary lives in the :doc:`glossary`, but most of it should be
fairly self-explanatory. Details about the providers are available in the
:doc:`providers` section.

Usage Lifecycle
---------------

.. only:: not latex

   .. figure:: _static/concepts-lifecycle.svg
      :alt: Discover once, then an optional repo sync, refresh, and store to the cache on each run
      :align: center

      Discover once, then refresh on demand. Reporting reads from the cache.

Working with your hosts follows a simple loop:

1. **Discover**: connect once and detect the operating system, version,
   flavor and package manager, then assign the right provider. You only repeat
   this if something fundamental changes on the host.
2. **Refresh**: ask the provider what updates are available, sort out which
   ones are security-related, and note whether a reboot is pending. This is
   entirely read-only.
3. **Repository Sync** *(optional)*: refresh the host's own package metadata
   first, so the next Refresh sees the very latest. This is the one step that
   may require :doc:`sudo` on some platforms.
4. **View / Report**: look at the results, via the :doc:`cli` status tables,
   the interactive :doc:`ui`, or generated :doc:`reports <reporting>`.

Everything Discover and Refresh learn is saved to a local **cache**, so viewing
status and generating reports never needs to touch the hosts again. This is
handy for scheduled reports, or simply running from a context where your SSH
agent is not available. See :doc:`cachefile` for more details.

What Exosphere Is Not
---------------------

Exosphere reports --- it does not act. It will happily tell you what needs
patching, where, and how urgently, but it will never apply an update or change
a host's configuration on your behalf. Pushing those changes out is left to
existing tooling built for the job, such as `Ansible`_ and similar automation
frameworks, or `unattended-upgrades`_ and similar.

See the :doc:`faq` for more on this distinction, and why it is a deliberate one.

.. _Ansible: https://www.ansible.com/
.. _unattended-upgrades: https://wiki.debian.org/UnattendedUpgrades
