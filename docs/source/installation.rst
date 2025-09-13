Installation
=============

Exosphere is written in Python, and can easily be installed using a handful
of methods. This guide will walk you through the installation process for each
of them.

Supported Platforms
-------------------

Exosphere is designed to be platform agnostic, and can be run nearly
everywhere Python runs. This guide can be used to install Exosphere on
the following platforms:

- Linux (any)
- FreeBSD
- MacOS
- Windows

Platform specific notes will appear whenever relevant, but the process
should be the same across all platforms.

Exosphere technically supports more platforms than the ones listed above,
but these are the ones we have explicitly tested. You can still follow
the instructions below in most cases, but your mileage may vary.

Installing from PyPI
----------------------

Exosphere is available on the `Python Package Index`_ (PyPI) for convenience,
and can be installed using various methods.

The package name is `exosphere-cli`.

.. admonition:: Note

    Exosphere requires **Python 3.13 or later** to run.
    If you do not have it available on your system, you can still install
    Exosphere using `uv`_, which will download and manage the necessary Python
    runtime and dependencies for you.


.. tabs::

    .. group-tab:: pipx

        This is the recommended way to install Exosphere, as it creates a
        virtual environment and isolates the application. You can install
        ``pipx`` from your distribution's repositories.

        .. code-block:: bash

            pipx install exosphere-cli

    .. group-tab:: uv

        If you do not have Python 3.13 or later available, you can use `uv`_ to
        install Exosphere. Click the link above to see how to install `uv` for
        your platform, and then simply run:

        .. code-block:: bash

            uv tool install exosphere-cli

        `uv tool` will handle downloading and installing the necessary Python
        runtime and dependencies for you, and then make the `exosphere`
        command available in your PATH.


The ``pipx`` or ``uv tool`` methods are recommended as they create a virtual
environment and isolate the application, making it readily available without
having to contend with potential conflicts with other Python packages.

The main difference is that ``uv tool`` will also download and manage the necessary
Python runtime for you, if you do not have a suitable version available.

``pip install`` is **not recommended** outside of a venv, as it *will* interfere
with other Python packages and system versions of the libraries, and many
distributions will in fact not allow you to install it that way.

Once installed, you can run Exosphere using the `exosphere` command, like so:

.. code-block:: bash

    exosphere --help


Installing from Git Repository
------------------------------

This is likely the easiest method if you want to track the latest development
version, or are simply more comfortable with using Git.

The project is setup with `uv`_, which will download and install the necessary
python runtime and dependencies for you, so you don't have to worry about
any of this.

You will require the following tools installed:

- `git`_ - to clone the repository
- `uv`_ - to install the application and manage its dependencies

First, Clone the repository into a directory of your choice.

.. tabs:: 

    .. group-tab:: HTTPS

        .. code-block:: text

            git clone https://github.com/mrdaemon/exosphere.git


    .. group-tab:: SSH

        .. code-block:: text

            git clone git@github.com:mrdaemon/exosphere.git

Then, change into the cloned directory:

.. code-block:: bash

    cd exosphere

If you want the stable version, you can switch to the latest tag.

.. tabs::

    .. group-tab:: Stable Release

        This will fetch the code for the latest stable release of Exosphere.
        This is recommended for most users.

        .. parsed-literal::

            git checkout |CurrentVersionTag|

        You can substitute |CurrentVersionTag| with a specific tag or
        version to use a specific release, e.g, `v0.8.1`.

        You can find the list of tags on the `GitHub releases page`_.

    .. group-tab:: Latest Development

        If you want the latest development version, you can switch to the
        `main` branch. This is not recommended for most users, as it may
        contain unstable or untested code.

        If you want to hack on Exosphere, or get the latest features
        even if they are not fully tested, you should use the `main` branch.

        .. code-block:: bash

            git checkout main

    
Once that is done, you can simply setup Exosphere using `uv`_:

.. code-block:: text

    uv sync --no-dev

This will download and install the necessary Python runtime and dependencies.

You can then either run Exosphere through `uv`_:

.. code-block:: text

    uv run --no-dev exosphere

Or, you can activate the virtual environment created by `uv`_ and run
Exosphere directly:

.. tabs::

    .. group-tab:: Unix/MacOS

        .. code-block:: text

            source .venv/bin/activate
            exosphere

    .. group-tab:: Windows/PowerShell

        .. code-block:: text

            . .venv\Scripts\activate.ps1
            exosphere

    .. group-tab:: Windows/cmd

        .. code-block:: text

            .venv\Scripts\activate.bat
            exosphere


    From that point on, you can run Exosphere using the `exosphere` command.


Updating Exosphere
===================

Updating Exosphere is generally as simple as installing it, depending on the installation
method you used.

From PyPI
---------


.. tabs::

    .. group-tab:: pipx

        If you installed Exosphere using `pipx`, you can update it with:

        .. code-block:: bash

            pipx upgrade exosphere-cli

    .. group-tab:: uv

        If you installed Exosphere using `uv`, you can update it with:

        .. code-block:: bash

            uv tool upgrade exosphere-cli


From Git Repository
-------------------

If you installed Exosphere from the Git repository, you can update it by
pulling the latest changes and then syncing with `uv`_:

.. tabs::

    .. group-tab:: Stable Release

        If you are on a stable release, you can update it with:

        .. parsed-literal::

            git fetch --tags
            git checkout |CurrentVersionTag|
            uv sync --no-dev

        You can substitute |CurrentVersionTag| with the latest tag or
        specific version you want to use, e.g, `v0.8.1`.

        You can find the list of tags on the `GitHub releases page`_.

    .. group-tab:: Latest Development

        If you are on the `main` branch, you can update it with:

        .. code-block:: bash

            git pull --rebase
            uv sync --no-dev
            

That's it! Your installation of Exosphere is now up to date.

.. _git: https://git-scm.com/
.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _Python Package Index: https://pypi.org/project/exosphere-cli/
.. _GitHub releases page: https://github.com/mrdaemon/exosphere/releases
