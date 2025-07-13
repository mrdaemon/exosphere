Welcome to Exosphere
=====================

Exosphere is a utility program for aggregating and reporting state of
patches/security updates as well as basic online status for Unix-like
hosts on a network.

It essentially allows you to have a single, centralized view of the
state of your hosts, and what pending patches or package updates are
available for them.

It has both a very nice interactive command line interface (CLI)
as well as a Text UI with menus and tables.

Exosphere is designed to abstract away the technical details involved in
obtaining this information, presenting consistent views of the state
across supported operating systems.

The application is written in Python and is designed to be platform
agnostic, and can be run nearly everywhere Python runs, including
Linux, BSDs, MacOS and Windows.

Supported operating systems and Package Managers for systems that
exosphere can query and manage include:

- Debian/Ubuntu and Derivatives (Apt)
- Red Hat/CentOS/Alma/Rocky and Derivatives (Yum/DNF)
- FreeBSD (pkg)

Connectivity to hosts is handled via SSH.

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
   glossary

.. toctree::
   :maxdepth: 2
   :caption: API Documentation:

   api/index
