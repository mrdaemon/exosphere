Welcome to Exosphere
=====================

Exosphere offers aggregated patch and security update reporting as
well as basic system status across multiple Unix-like hosts via SSH.

.. figure:: _static/demo.gif
   :alt: Exosphere demo
   :align: center

   Exosphere demo

It is targeted at small to medium sized networks.

It is meant to be simple to deploy and use, requiring no central server,
agents or complex dependencies on remote hosts.

If you have SSH access to the hosts with an `agent`_, you are good to go!

**Key Features**

- Rich interactive command line interface (CLI)
- Text-based user interface (TUI) offering menus, tables and dashboards
- Consistent view across different platforms and package managers
- See everything in one spot, at a glance, without complex automation
  or enterprise solutions.
- Document-based reporting in HTML, text or markdown format
- JSON output available for integration with other tools


**Compatibility**

- **Exosphere**: Linux, BSDs, macOS, Windows (and more!)
- **Remote**: Debian/Ubuntu-likes, RedHat-Likes, FreeBSD, OpenBSD

.. note::

   For more details on supported platforms, see the :doc:`supportedos` page.

Exosphere is written in Python and abstracts away the technical details
of collecting this information across platforms, allowing you to focus
on management of your systems.

You can get started with :doc:`installation` and then follow up
with the :doc:`quickstart` to get an overview of how to use Exosphere.

:doc:`configuration` details are also available, alongside the
:doc:`api/index` if you wish to implement your own providers.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   concepts
   installation
   quickstart
   supportedos

.. toctree::
   :maxdepth: 2
   :caption: Using Exosphere

   cli
   ui
   reporting

.. toctree::
   :maxdepth: 2
   :caption: Administration

   connections
   configuration
   sudo
   cachefile

.. toctree::
   :maxdepth: 2
   :caption: Support

   troubleshooting
   faq
   gettinghelp

.. toctree::
   :maxdepth: 2
   :caption: Reference

   providers
   command_reference
   glossary

.. toctree::
   :maxdepth: 2
   :caption: Developer Documentation

   api/index


.. _agent: https://en.wikipedia.org/wiki/Ssh-agent
