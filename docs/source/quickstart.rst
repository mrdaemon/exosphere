Quickstart Guide
================

After :doc:`Installing Exosphere<installation>`, you can quickly get started by
following this guide and adapting the simple scenario it presents to your needs.

Scenario
--------

Let's assume you have a handful of hosts on your network, and you wish to use Exosphere
to keep track of their updates and basic online status, and get reporting on them.

For this example, we will assume you have the following hosts:

- `db1.example.com`: A Debian-based database server
- `web1.example.com`: A RedHat-based web server
- `files.example.com`: A FreeBSD-based file server

Your username on all of those hosts is `admin`, and you have SSH access to them via
public key authentication, with your keys loaded into your SSH Agent.

.. admonition:: Note

    If you do not have an SSH Agent configured with your keys loaded,
    authentication to the hosts will fail. They can be configured
    easily on Linux, MacOS and Windows. 
    See the :doc:`connections` documentation for more details.

Configuration
--------------

To get started, you will first need to create a configuration file for Exosphere.
The configuration file will contain your **Options** as well as the **Inventory**, 
which is the list of hosts you want to manage, and any host specific settings
they may need.

Execute the following command to see in which directory it is meant to be created:

.. code-block:: console

    $ exosphere config paths
    Application directories:

    Config: <your_config_directory>
    State: <your_state_directory>
    Log: <your_log_directory>
    Cache: <your_cache_directory>

Simply create file named `config.yaml` in the directory shown as `Config` in the output of
the command above.

.. note::

    You can also name the file `config.toml` or `config.json` to use the
    TOML and JSON formats, respectively, and we will give the examples in
    all formats, but if you are not familiar with any of them, YAML is
    fine.


Setting up our basic options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We will first create an ``options`` section in the configuration file, where we will
set the only option we need for this example, the ``default_username`` option, which
will configure the default SSH username to use when connecting to hosts.

.. admonition:: Note

    You do not strictly need to set this option, by default, you local username
    will be used to connect to hosts. 
    
    If that suits you, you can omit the ``options``  section entirely from the
    config file. For a full list of options,
    see :doc:`the configuration documentation<configuration>`.

.. tabs::

    .. group-tab:: YAML

        .. code-block:: yaml

            options:
              default_username: admin

    .. group-tab:: TOML

        .. code-block:: toml

            [options]
            default_username = "admin"

    .. group-tab:: JSON

        .. code-block:: json

            {
                "options": {
                    "default_username": "admin",
                }
            }


Configuring our Inventory
^^^^^^^^^^^^^^^^^^^^^^^^^

We will then configure our hosts in a ``hosts`` section in the configuration file.

We need two mandatory pieces of information for each host, the ``name`` and the ``ip`` address
or DNS hostname of the host.

Optionally, we can also add a ``description`` field to
add a description for ourselves so we know what the host is, but this is not required.

.. tabs::

    .. group-tab:: YAML

        .. code-block:: yaml

            hosts:
            - name: db1
              ip: db1.example.com
              description: Debian database server # Optional
            - name: web1
              ip: web1.example.com
              description: RedHat web server # Optional
            - name: files
              ip: files.example.com
              description: FreeBSD file server # Optional

    .. group-tab:: TOML

        .. code-block:: toml

            [[hosts]]
            name = "db1"
            ip = "db1.example.com"
            description = "Debian database server" # Optional

            [[hosts]]
            name = "web1"
            ip = "web1.example.com"
            description = "RedHat web server" # Optional

            [[hosts]]
            name = "files"
            ip = "files.example.com"
            description = "FreeBSD file server" # Optional

    .. group-tab:: JSON

        .. code-block:: json

            {
                "hosts": [
                    {
                        "name": "db1",
                        "ip": "db1.example.com",
                        "description": "Debian database server" // Optional
                    },
                    {
                        "name": "web1",
                        "ip": "web1.example.com",
                        "description": "RedHat web server" // Optional
                    },
                    {
                        "name": "files",
                        "ip": "files.example.com",
                        "description": "FreeBSD file server" // Optional
                    }
                ]
            }

.. note:: **What if my username is not the same on all hosts?**

    Don't worry! You can set the ``username`` option on a per host basis.
    Additionally, if you omit it, it will use your current username.
    See the :ref:`host options docs<hosts_options_section>` for more details
    with examples, as well as the :doc:`connections` section.

Your full configuration file would now look like this:

.. tabs::

    .. group-tab:: YAML

        .. code-block:: yaml

            options:
              default_username: admin

            hosts:
            - name: db1
              ip: db1.example.com
              description: Debian database server # Optional
            - name: web1
              ip: web1.example.com
              description: RedHat web server # Optional
            - name: files
              ip: files.example.com
              description: FreeBSD file server # Optional

    .. group-tab:: TOML

        .. code-block:: toml

            [options]
            default_username = "admin"

            [[hosts]]
            name = "db1"
            ip = "db1.example.com"
            description = "Debian database server" # Optional

            [[hosts]]
            name = "web1"
            ip = "web1.example.com"
            description = "RedHat web server" # Optional

            [[hosts]]
            name = "files"
            ip = "files.example.com"
            description = "FreeBSD file server" # Optional

    .. group-tab:: JSON

        .. code-block:: json

            {
                "options": {
                    "default_username": "admin",
                },
                "hosts": [
                    {
                        "name": "db1",
                        "ip": "db1.example.com",
                        "description": "Debian database server" // Optional
                    },
                    {
                        "name": "web1",
                        "ip": "web1.example.com",
                        "description": "RedHat web server" // Optional
                    },
                    {
                        "name": "files",
                        "ip": "files.example.com",
                        "description": "FreeBSD file server" // Optional
                    }
                ]
            }

