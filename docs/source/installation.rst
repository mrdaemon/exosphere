Installation
=============

Exopshere is a Python package, and **requires** Python 3.13 or later to run.
Given that this particular version of Python is not widely available on
some operating systems, we provide multiple options for installation.

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


Installing from PyPI
----------------------

Exosphere is available on the `Python Package Index`_ (PyPI) for convenience,
and can be installed using various methods.

One major pitfall here is that Exosphere **requires Python 3.13 or later**.

If you do not have Python 3.13 or later available on your system, fear not,
you can still install Exosphere using `uv`_, which will download and manage
the necessary Python runtime and dependencies for you.

.. tabs::

    .. group-tab:: pipx

        This is the recommended way to install Exosphere, as it creates a
        virtual environment and isolates the application.

        .. code-block:: bash

            pipx install exosphere

    .. group-tab:: uv

        If you do not have Python 3.13 or later available, you can use `uv`_ to
        install Exosphere. Click the link above to see how to install `uv` for
        your platform, and then simply run:

        .. code-block:: bash

            uv tool install exosphere

        `uv`_ will handle downloading and installing the necessary Python
        runtime and dependencies for you, and then make the `exosphere`
        command available in your PATH.

    .. group-tab:: pip

        If you prefer to use `pip`, you can install Exosphere globally or
        for your user only. However, this is not recommended as it may
        lead to conflicts with other Python packages.

        .. code-block:: bash

            pip install --user exosphere

The `pipx` command is recommended as it creates a virtual environment and
isolates the application, making it readily available without having to
contend with potential conflicts with other Python packages.


Installing from Git Repository
------------------------------

This is likely the easiest and best option if you **don't** have Python 3.13
or later available, or want to hack on Exosphere itself.

The project is setup with `uv`_, which will download and install the necessary
python runtime and dependencies for you, so you don't have to worry about
any of this.

You will require the following tools installed:

- `git`_ - to clone the repository
- `uv`_ - to install the application and manage its dependencies

.. _git: https://git-scm.com/
.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _Python Package Index: https://pypi.org/project/exosphere/


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
        This is recommend for most users.

        .. parsed-literal::

            git checkout |CurrentVersionTag|

    .. group-tab:: Latest Development

        If you want the latest development version, you can switch to the
        `main` branch. This is not recommended for most users, as it may
        contain unstable or untested code.

        If you want to hack on Exosphere, or get the latest features
        even if they are not fully tested, you should use the `main` branch.

        .. code-block:: bash

            git checkout main



