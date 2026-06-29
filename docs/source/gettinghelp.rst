Getting Help
============

While exosphere is provided as-is, with no expectation of warranty or support,
there are a few resources available for help if you run into issues or have questions.

Before reaching out
-------------------

Common issues are already covered in the following places:

* The :doc:`troubleshooting` walks through diagnosing the common failures.
* The :ref:`FAQ <faq-troubleshooting>` collects specific symptoms and their fixes.

It is worth a quick pass through both --- the answer is often there, and if it
is not, the steps you already tried are exactly what helps someone help you.

Asking a question
-----------------

For usage questions, "how do I...", ideas, or just to share what you have built,
use `GitHub Discussions`_. This is the best place for anything that is not
clearly a bug.

Reporting a bug
---------------

If you have found a bug, please open an issue using the `bug report form`_.

To make it actionable, include as much of the following as you can:

* **The Exosphere version** you are running:

  .. code-block:: console

      $ exosphere version check

* **Your platform**: the operating system you run Exosphere on, and the
  remote platform(s) involved.
* **Relevant log output**: Reproduce the problem with
  :ref:`log_level <log_level_option>` set to ``DEBUG``, then attach the relevant
  portion of the log file (find it via ``exosphere config paths``).
* **A sanitized configuration snippet**, or the output of ``exosphere config diff``,
  so the relevant options are visible. Remove anything sensitive first.
* **Steps to reproduce**, along with what you expected versus what actually
  happened.

For problems with updates or repository sync on a specific platform, the
:doc:`providers` page lists the exact commands Exosphere runs --- running the
failing one by hand on the remote host and including its output is incredibly
helpful.

Feature requests and ideas
--------------------------

Suggestions are welcome. Open a discussion on `GitHub Discussions`_, or an issue
via the `bug report form`_ --- whichever feels more appropriate. If you have
built something neat on top of Exosphere's :doc:`reporting` (a dashboard, a bot,
a coffee-brewing cron job), we would love to hear about it.

.. _GitHub Discussions: https://github.com/mrdaemon/exosphere/discussions
.. _bug report form: https://github.com/mrdaemon/exosphere/issues/new/choose
