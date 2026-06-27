Frequently Asked Questions
==========================

And also troubleshooting tips, in general.

Can Exosphere help me apply the updates and patches?
----------------------------------------------------

Unfortunately, no. Exosphere is not a configuration management or automation
tool, simply a reporting and aggregation tool.

The gap it exists to fill is providing you with a unified, centralized view
of the `state` of updates and patches across your systems, so you can
make informed decisions about what needs patching, and when.

This functionality is not planned, and left to frankly better tooling that
already exists, such as `UnattendedUpgrades`_, `Ansible`_, `RunDeck`_, etc.

I really like the dashboard. Can I still use it if my systems are unsupported?
------------------------------------------------------------------------------

Yes, as long as the remote system is a Unix-like operating system.

In this case, if your remote operating system is not supported, Exosphere will allow
you to use the dashboard and online checks (ping command, etc) just fine.

You won't be able to perform refresh or sync operations on them, and the update
counts will be disabled, but this part will remain functional.

If the system in question is not a Unix-like operating system, it will not
be discoverable at all, and should not be added to the inventory.

Why does ping report Offline when the system is reachable?
----------------------------------------------------------

The ``ping`` checks in exosphere aren't ICMP ping, but SSH pings.
They will only return an Online status if the remote system can be
connected to successfully, over SSH, and a simple POSIX test command
can be executed. (``/bin/true`` or shell built-in equivalent)

As such, scenarios that can cause an Offline status include:

* SSH Authentication Failure (bad username, invalid credentials)
* Timeouts and Connectivity Errors
* Failure to execute the supremely basic test command

We consider "Online" to mean "the system is up and ready to process further queries",
instead of just "the system is reachable over the network".

This is by design, and aims to avoid scenarios where the system is reachable,
but is currently shutting down, or has not finished booting.

Generally, if the host shows up as Offline, you would not be able to
perform any of the other operations on it anyways.

You can re-run the ``discovery`` command to find out what the issue is and
correct it, if you are getting this during initial setup.

Can I specify a custom path for the configuration file?
-------------------------------------------------------

Yes! You can specify a custom path for the configuration file by setting the
``EXOSPHERE_CONFIG_FILE`` environment variable to the full path of the file you wish to use.

See :doc:`configuration` for more details on other environment variables
you can define to influence or override the configuration.

I get an error with "Private key file is encrypted", what does it mean?
-----------------------------------------------------------------------

The presence of this error in logs means that authentication failed in some way.

Verify that:

- The server has Public Key Authentication enabled
- Your SSH agent is running and has the correct key loaded
- The right user name is being used to connect

The unhelpful error message is unfortunately `Known Issue`_ in the `paramiko`
library, which is used internally to handle SSH connections. Whenever
authentication fails when an SSH agent is used, this is the exception
that will be raised, regardless of the actual issue.

Exosphere will generally catch this specific error and rewrite the error message
to be more helpful, but there are a few edge cases where it may be displayed as-is.

My system using `dnf` or `yum` hangs when refreshing
----------------------------------------------------

The `dnf` and `yum` providers do a best effort to prevent interactive
prompts when running the commands they need to synchronize repositories
and cache, but sometimes, they will still prompt for user input, which
Exosphere cannot handle.

To resolve this, you can simply connect to the remote system as the same
user you use within Exosphere, and manually run the following commands:

.. tabs::

    .. group-tab:: dnf

        .. code-block:: bash

            dnf makecache --refresh
            dnf check-update

    .. group-tab:: yum
        .. code-block:: bash

            yum makecache --refresh
            yum check-update

And answer all the prompts that may appear. The provider should no longer hang
past this point.

After an update, my system using `dnf` fails to refresh!
--------------------------------------------------------

After certain types of updates, you may get the following error message when
trying to refresh a `dnf` based system:

.. code-block:: text

    Failed to get current versions: Error: SQLite error on "/var/lib/dnf/history.sqlite":
    Executing an SQL statement failed: attempt to write a readonly database

This is a known issue where `dnf` apparently needs to perform some database
updates before it can perform its queries. This requires root privileges, which
Exosphere does not have access to during normal operations.

To resolve this, you can connect to the remote system and run a simple query
with root privileges to fix the database:

.. code-block:: bash

    $ sudo dnf --quiet -y list installed kernel.x86_64

This should resolve the issue, and you should be able to refresh the system
without write access errors afterwards.

I've tuned the timeout but this one host keeps getting flagged offline
----------------------------------------------------------------------

Exosphere does use a fairly aggressive timeout value for its SSH connections,
but if you have a host that is consistently supremely slow to respond, yet you
can connect to it reliably, it is likely you have DNS issues on that server.

Check your resolvers and/or add ``UseDNS no`` to your sshd configuration.
FreeBSD notoriously ships with the option enabled by default, for instance.

If you can't or this has no effect, you can increase the timeout value for
that host specifically by setting the ``connect_timeout``
:ref:`host option <connect_timeout_host_option>` to a higher value, without
having to change the global option.

The frequent SSH connections are causing issues on my SSH server
----------------------------------------------------------------

If you have systems that have connection rate limiting, or take a while
to authenticate, you can enable SSH connection pipelining to reduce
the amount of connection churn.

See the :ref:`documentation on SSH Pipelining <ssh_pipelining_docs>` as
well as the :ref:`ssh_pipelining configuration option <ssh_pipelining_option>`.

I don't like the ascii art banner in interactive mode
-----------------------------------------------------

You can disable it entirely with the ``no_banner``
:ref:`config option <no_banner_option>`.

After upgrading to 3.0, my old shell completion misbehaves
----------------------------------------------------------

Exosphere can install tab-completion for **zsh**, **bash** and **fish** with:

.. code-block:: console

   exosphere --install-completion

Versions prior to **3.0** generated completion differently (via Typer) and
wrote the scripts to *different* locations. Re-running ``--install-completion``
installs the new script alongside the old one rather than replacing it, so the
stale files from the previous version are left behind.

For all cases **except PowerShell**, the new completion takes precedence and
the leftovers are harmless, but it is cleanest to remove them. If a stale script
ever did take precedence, it would try to run ``exosphere`` at completion time and
drop into the interactive REPL, appearing to hang your shell.

To clean up the previous version's files:

- **bash**: delete ``~/.bash_completions/exosphere.sh`` and remove its
  ``source`` line from ``~/.bashrc``.
- **zsh**: delete ``~/.zfunc/_exosphere`` (the new script is installed under
  ``~/.zsh/completions``, or your oh-my-zsh completions directory).
- **fish**: nothing to do — the new script overwrites the old one at the
  same path.

.. attention::

   Typer also supported PowerShell completion, but Exosphere 3.0 does **not**.
   This makes cleanup *required* on PowerShell rather than optional: with no
   new completion to replace it, the stale Typer completer remains active and
   *will* try to run ``exosphere`` at completion time, dropping into the REPL
   and appearing to hang your shell.

   Typer appended its completion directly into your PowerShell profile (rather
   than a separate file). To remove it, open the profile:

   .. code-block:: powershell

      notepad $PROFILE

   and delete the Exosphere completion block, which looks roughly like:

   .. code-block:: powershell

      Import-Module PSReadLine
      Set-PSReadLineKeyHandler -Key Tab -Function MenuComplete
      $scriptblock = {
          param($wordToComplete, $commandAst, $cursorPosition)
          $Env:_EXOSPHERE_COMPLETE = "complete_powershell"
          # ... several lines referencing exosphere ...
      }
      Register-ArgumentCompleter -Native -CommandName exosphere -ScriptBlock $scriptblock

   Remove the ``$scriptblock`` assignment and the matching
   ``Register-ArgumentCompleter ... -CommandName exosphere`` line. You can
   leave the generic ``Import-Module PSReadLine`` /
   ``Set-PSReadLineKeyHandler`` lines if other tools rely on them. Restart
   PowerShell afterwards.

When managing Ubuntu systems, will this handle snaps?
-----------------------------------------------------

Exosphere does not currently support snaps or flatpaks.
There are no immediate plans to add support for these, but it is certainly possible
in the future, if this becomes a common facet of server management.

On BSD systems, will this handle system updates and source ports?
-----------------------------------------------------------------

Exosphere does not currently support system updates or source ports.
It only supports Binary Packages, for both FreeBSD and OpenBSD.

There are plans to add support for system updates in the future, presenting
them as a synthetic package in the updates view, but this needs more work.

For the time being, cron reports and mailing lists for `syspatch` and
`freebsd-update` are recommended to keep tabs on these.

Does FreeBSD support extend to things like OPNSense?
-----------------------------------------------------

Since **1.3.4**, the ``pkg`` provider performs repository synchronization in a
manner that is compatible with OPNSense, and the platform is supported
as FreeBSD.

As long as you configure sudo and sudoers correctly, and that the system
uses ``pkg`` underneath, it should work just fine.

Updates refresh fails on my OpenBSD system with an exotic architecture!
-----------------------------------------------------------------------

Exosphere relies on the availability of the ``syspatch`` command to determine
if the system is tracking a stable release or `-current`.

If you're running a more exotic, non-x86 architecture, Exosphere may not
be able to handle the failure mode gracefully, and we'd deeply appreciate
it if you could `file a bug report`_ with the output of ``syspatch -l``
so we can improve this situation.

Help, the sudoers snippet I generated does not work!
----------------------------------------------------

The usual checklist for files in sudoers.d applies here:

- The file must be owned by root
- Must have permissions of 0440
- Must not contain syntax errors (check with `visudo -c -f /etc/sudoers.d/yourfile`)

If you are still having issues, a common problem is another rule matching last.
Sudo reads rules in lexicographic order (i.e., not strictly alphabetical), but does not
merge them, and the last matching rule wins.

You can verify ordering with `visudo -c` and find out which rule is matching
last with:

.. code-block:: bash

    sudo -l -U youruser /the/sudo/command --and --args

and compare with the output of ``sudo -ll`` to see which rule matched vs which was expected.

You can find which exact command exosphere is trying to run in the :doc:`providers`
documentation.

A quick workaround for ordering issues is to just name the generated snippet with a prefix
that ensures it is loaded and matched last, for instance:

``/etc/sudoers.d/zz-exosphere``

Is there any way to disable the update check?
---------------------------------------------

Yes, you can disable the update check by setting the ``update_checks``
:ref:`config option <update_checks_option>` to ``false`` in the
configuration file.

This should be helpful in environments where you do not want to talk to
PyPI at all.

If you are a prospective package maintainer wishing to package Exosphere
for your favorite platform's repositories, it is recommended that you patch
out the default value of this option to ``False`` in ``exosphere/config.py``,
or override via :ref:`environment variables <config_env_vars>`, if feasible.

Is Windows support planned or even possible?
------------------------------------------------

The application runs fine on Windows, and while managing Windows is something we would love
to implement, the connection methods are not incredibly straightforward, and the APIs and
interfaces for update and patch management are not great. Microsoft continues to hope you
will buy into their management tools, so the core APIs are not very accessible as a result.

Windows support remains an eventual goal, but it is not currently planned.

Why all the different config file formats?
------------------------------------------

The author is fond of yaml, but recognizes toml is gaining traction in the Python community.
At this point also supporting json was so low effort that it was added in.

The overhead of supporting this is so negligible that we'd prefer to make everyone
happy, if at all possible.

They all de-serialize to exactly the same data structure (and this is validated with unit tests),
so you can use whichever of the formats you feel strongest about, or hate the least.

Didn't Exosphere used to have a Web UI? What happened to it?
------------------------------------------------------------

It was removed in version 3.0. The Web UI started as a neat curiosity more than
a feature, but never left the experimental stage.

It was always provided as a separate, opt-in, extra for the python packages,
and installed and used by few, least of all the author.

As the project matured, and new features started clashing with the way it was
implemented, it became clear it should be removed instead of being left to rot
in its current, janky, underdeveloped state.

Why Python 3.13?
----------------

For completely selfish reasons such as:

- Wanting to use the latest and greatest Python features
- Not wanting to bother with multi version support

Exosphere was written mostly to scratch the author's own itch.
While it is made public in the hopes that it will be useful to others,
and great care and effort has been spent on documentation and ease of use,
the focus at this time remains to keep the author happy.

Compatibility test matrices are unfortunately not a source of happiness.

.. _UnattendedUpgrades: https://wiki.debian.org/UnattendedUpgrades
.. _Ansible: https://www.ansible.com/
.. _RunDeck: https://www.rundeck.com/
.. _Known Issue: https://github.com/paramiko/paramiko/issues/387
.. _file a bug report: https://github.com/mrdaemon/exosphere/issues
