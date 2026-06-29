Troubleshooting Guide
=====================

When something is not working as expected, this guide walks through how to
diagnose the problem, starting from the tools Exosphere gives you and working
toward the most common causes.

For specific symptoms and their fixes, see the :ref:`FAQ <faq-troubleshooting>`.
If you work through both and are still stuck, :doc:`gettinghelp` points you at the
right place to ask, or submit a bug report.

Check the logs
--------------

Exosphere always writes a log file, regardless of how you run it, and it is the
first place to look. To find it, run:

.. code-block:: console

    $ exosphere config paths

and look under the ``Log:`` entry for the path on your platform.

If you are in the :doc:`TUI <ui>`, you can also press ``l`` to open the Logs
screen and watch events as they happen.

Turn up the verbosity
---------------------

By default, Exosphere logs at ``INFO`` level. If the logs do not explain the
problem, raise it to ``DEBUG`` via the :ref:`log_level <log_level_option>`
option:

.. tabs::

    .. group-tab:: YAML

        .. code-block:: yaml

            options:
              log_level: DEBUG

    .. group-tab:: TOML

        .. code-block:: toml

            [options]
            log_level = "DEBUG"

    .. group-tab:: JSON

        .. code-block:: json

            {
                "options": {
                    "log_level": "DEBUG"
                }
            }

You can also raise it for a single run, without editing your config, via the
``EXOSPHERE_OPTIONS_LOG_LEVEL`` :ref:`environment variable <config_env_vars>`.

.. tabs::

    .. group-tab:: Unix/macOS

        .. code-block:: console

            $ EXOSPHERE_OPTIONS_LOG_LEVEL=DEBUG exosphere

    .. group-tab:: Windows/PowerShell

        .. code-block:: powershell

            $env:EXOSPHERE_OPTIONS_LOG_LEVEL = "DEBUG"
            exosphere

    .. group-tab:: Windows/cmd

        .. code-block:: batch

            set EXOSPHERE_OPTIONS_LOG_LEVEL=DEBUG
            exosphere

You can confirm this worked by checking the output of ``exosphere config source``
and ``exosphere config diff``.

For library-level detail (the SSH internals from Fabric and paramiko, for
instance), there is the :ref:`debug <debug_option>` option, but be warned that
it is extremely noisy and is rarely needed outside of development. We suggest not
using this unless asked in a bug report.

Check the configuration Exosphere actually loaded
-------------------------------------------------

A surprising number of "it is not doing what I told it to" problems come down to
Exosphere loading a different configuration file than you expect, or an
environment variable quietly overriding a value.

Confirm what was loaded, and from where:

.. code-block:: console

    $ exosphere config source

This shows the active configuration file path and any environment variables
influencing the configuration. To inspect the effective values, use
``config show``, or ``config diff`` to see only what differs from the defaults.

Test connectivity
-----------------

Most failures are connectivity or authentication problems. The quickest test is
a discovery, which prints a clear table of any errors:

.. code-block:: exosphere

    exosphere> inventory discover

or, for a single host:

.. code-block:: exosphere

    exosphere> host discover bigserver

If a host fails, work through the checklist:

* Your SSH agent is running and has the right key loaded
* The username and port are correct (see :doc:`configuration`)
* The host is reachable and its SSH service is running
* The host allows public key authentication

To reproduce the connection outside of Exosphere, with full detail:

.. code-block:: console

    $ ssh -vvv bigserver

Remember that Exosphere honors ``~/.ssh/config`` and ``/etc/ssh/ssh_config``, so
double-check any host aliases or per-host settings there. The :doc:`connections`
page covers all of this in depth.

.. tip::

    A host shown as **Offline** is not an ICMP ping failure --- Exosphere
    considers a host online only if it can open an SSH session and run a trivial
    command. We consider "Online" to mean in a state where it could execute further
    commands and queries, which implies end-to-end ssh connectivity.

Common situations
-----------------

A few recurring issues, with where to look:

* **A host is flagged Offline but you can reach it** --- usually slow DNS on the
  remote ``sshd``; the :ref:`FAQ <faq-troubleshooting>` covers the ``UseDNS no`` fix and the per-host
  :ref:`connect_timeout <connect_timeout_host_option>` option.
* **"Private key file is encrypted"** --- an authentication failure in disguise;
  the :ref:`FAQ <faq-troubleshooting>` explains the underlying cause.
* **A** ``dnf`` **or** ``yum`` **host hangs or errors on refresh** --- the
  :ref:`FAQ <faq-troubleshooting>` has the manual ``makecache`` workaround and the read-only database
  fix.
* **Frequent connections upset your SSH server** --- enable
  :ref:`SSH pipelining <ssh_pipelining_docs>` to cut down on connection churn.
* **A generated sudoers snippet does not work** --- the :ref:`FAQ <faq-troubleshooting>` has the
  ownership, permissions, and rule-ordering checklist.

When to look at the providers
-----------------------------

If a host connects fine but updates or repository sync misbehave, the cause is
often specific to the package manager. The :doc:`providers` page documents the
exact commands each provider runs, along with platform quirks --- running the
failing command by hand on the remote host is often the fastest way to see what
is really going wrong.

Still stuck?
------------

If you have worked through this guide and the :ref:`FAQ <faq-troubleshooting>` without luck, head to
:doc:`gettinghelp` for where to ask and how to file a useful bug report.
