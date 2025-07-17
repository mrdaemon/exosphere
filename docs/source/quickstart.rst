Quickstart Guide
================

After :doc:`Installing Exosphere<installation>`, you can quickly get started by
following this guide and adapting the simple scenario it presents to your needs.

Create the Configuration File
-----------------------------

.. code-block:: bash

    $ exosphere config paths

Create one of ``config.yaml``, ``config.toml``, or ``config.json`` in the
`Config` directory shown here.


Basic configuration
--------------------

.. tabs::

    .. group-tab:: YAML

        .. code-block:: yaml

            # Username for SSH connections, optional
            # If not specified, the current user will be used
            options:
              default_username: admin

            # Hosts to manage
            hosts:
            - name: db1
              ip: db1.example.com
              description: RedHat database server
            - name: web1
              ip: web1.example.com
              description: Debian web server
            - name: files
              ip: 192.168.0.28 # ip is fine too
              port: 2222       # Optional port if not 22
              # description is optional

    .. group-tab:: TOML

        .. code-block:: toml

            # Username for SSH connections, optional
            # If not specified, the current user will be used
            [options]
            default_username = "admin"

            # Hosts to manage
            [[hosts]]
            name = "db1"
            ip = "db1.example.com"
            description = "RedHat database server"

            [[hosts]]
            name = "web1"
            ip = "web1.example.com"
            description = "Debian web server"

            [[hosts]]
            name = "files"
            ip = "192.168.0.28" # ip is fine too
            port = 2222         # Optional port if not 22
            # description is optional

    .. group-tab:: JSON

        .. code-block:: json

            {
                "options": {
                    "default_username": "admin"
                },
                "hosts": [
                    {
                        "name": "db1",
                        "ip": "db1.example.com",
                        "description": "RedHat database server"
                    },
                    {
                        "name": "web1",
                        "ip": "web1.example.com",
                        "description": "Debian web server"
                    },
                    {
                        "name": "files",
                        "ip": "192.168.0.28",
                        "port": 2222,
                    }
                ]
            }

.. admonition:: Note

    This assumes your public keys are loaded in your SSH agent.
    See :doc:`connections` for more details.


Run Exosphere
-------------

.. code-block:: console

    $ exosphere

At the exosphere prompt, you can run commands to manage your hosts.

Discover Hosts
--------------

.. code-block:: console

    exosphere> inventory discover
      [OK] db1
      [OK] web1
      [OK] files

This will detect the platform and package manager for each host.
It only needs done once, or if something changes on the host.

Refresh Updates
---------------

.. code-block:: console

    exosphere> inventory refresh
      [OK] db1
      [OK] web1
      [OK] files

This will retrieve the available updates and patches for each host.

View Update Status and Run Interface 
------------------------------------

.. code-block:: console

    exosphere> inventory status
                                    Host Status Overview
    ┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
    ┃ Host      ┃ OS      ┃ Flavor  ┃ Version         ┃ Updates ┃ Security ┃ Status  ┃
    ┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
    │ db1       │ linux   │ rhel    │ 9               │ 2       │ 0        │ Online  │
    │ web1      │ linux   │ debian  │ 12              │ 5       │ 1        │ Online  │
    │ files     │ freebsd │ freebsd │ 13.2-RELEASE-p3 │ 0       │ 0        │ Online  │
    └───────────┴─────────┴─────────┴─────────────────┴─────────┴──────────┴─────────┘
                                                                * indicates stale data
    
    exosphere> host show db1
    ╭─────────── Debian web server ────────────╮
    │ Host Name: web1                          │
    │ IP Address: web1.example.com             │
    │ Port: 22                                 │
    │ Online Status: Online                    │
    │                                          │
    │ Last Refreshed: Thu Jul 17 19:19:53 2025 │
    │ Stale: No                                │
    │                                          │
    │ Operating System:                        │
    │   debian linux 12, using apt             │
    │                                          │
    │ Updates Available: 2 updates, 0 security │
    │                                          │
    ╰──────────────────────────────────────────╯
                                     Available Updates
    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Name     ┃ Current Version      ┃ New Version          ┃ Security ┃ Source              ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
    │ crowdsec │ 1.6.9                │ 1.6.10               │ No       │ crowdsec:1/any      │
    │ nodejs   │ 22.17.0-1nodesource1 │ 22.17.1-1nodesource1 │ No       │ . nodistro:nodistro │
    └──────────┴──────────────────────┴──────────────────────┴──────────┴─────────────────────┘

There you go! You are now setup with a basic Exosphere configuration and can aggregate your
updates all in one place.

To go further, you can explore the various commands in the :doc:`cli` or start the full
:doc:`ui` for a more interactive experience:

.. code-block:: console

    $ exosphere ui start

