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

Yes. If your remote operating system is not supported, Exosphere will allow
you to use the dashboard and online checks (ping command, etc) just fine.

You won't be able to perform refresh or sync operation on them, and the update
counts will be disabled, but this part will remain functional.


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
authentication fails when a SSH agent is used, this is the exception
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

I've tuned the timeout but this one host keeps getting flagged offline
----------------------------------------------------------------------

Exosphere does use a fairly aggressive timeout value for its ssh connections,
but if you have a host that is consistently supremely slow to respond, yet you
can connect to it reliably, it is likely you have DNS issues on that server.

Check your resolvers and/or add ``UseDNS no`` to your sshd configuration.
FreeBSD notoriously ships with the option enabled by default, for instance.

If you can't or this has no effect, you can increase the timeout value for
that host specifically by setting the ``connect_timeout``
:ref:`host option <connect_timeout_host_option>` to a higher value, without
having to change the global option.

When managing Ubuntu systems, will this handle snaps?
-----------------------------------------------------

Exosphere does not currently support snaps or flatpaks.
There are no immediate plans to add support for these, but it is certainly possible
in the future, if this becomes a common facet of server management.

On FreeBSD systems, will this handle system updates and source ports?
---------------------------------------------------------------------

Exosphere does not currently support FreeBSD system updates or source ports.
It only supports FreeBSD Binary Packages, using `pkg`.

There are plans to add support for system updates in the future, presenting
them as a synthetic package in the updates view, but this needs more work.

Does FreeBSD support extends to things like OPNSense?
-----------------------------------------------------

Partially, but probably not in the way you expect. `Discover` will work and pick them up
as FreeBSD systems generally, but the `Updates` data may or may not contain things that are
actually of interest.

Generally, OPNsense, while it does use `pkg-ng` under the hood, tends to run it in a very specific
context when checking for package updates, and querying it from a user normally only sometimes
yields useful results for *some* packages, and only in certain contexts.

We'd love to extend this support, but it is not currently implemented. You can still add the
systems to the inventory, and you will get the Online checks, but the Updates view may not
actually contain OPNSense updates.

Is Windows support planned or even possible?
------------------------------------------------

The application runs fine on windows, and while managing Windows is something we would love
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
