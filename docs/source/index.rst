Welcome to Exosphere
=====================

Exosphere offers aggregated patch and security update reporting as
well as basic system status across multiple Unix-like hosts via SSH.

.. image:: _static/demo.gif
   :alt: Exosphere demo
   :align: center

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


**Compatibility**

- **Exosphere**: Linux, BSDs, MacOS, Windows (and more!)
- **Target systems**: Debian/Ubuntu-likes (apt), RedHat-Likes (yum/dnf), FreeBSD (pkg)

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
   :caption: User Documentation:

   installation
   quickstart
   supportedos
   connections
   configuration
   cli
   ui
   webui
   cachefile
   providers
   faq
   command_reference
   glossary

.. toctree::
   :maxdepth: 2
   :caption: API Documentation:

   api/index


.. _agent: https://en.wikipedia.org/wiki/Ssh-agent
