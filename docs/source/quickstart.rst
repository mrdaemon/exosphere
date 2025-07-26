Quickstart Guide
================

After :doc:`Installing Exosphere<installation>`, you can quickly get started by
following this guide and adapting the simple scenario it presents to your needs.

**Create the Configuration File**

.. code-block:: bash

    $ exosphere config paths

Create ``config.yaml`` in the `Config` directory shown here.

.. tip::

    You can also use `config.toml` or `config.json` if you prefer those formats.
    See the :doc:`configuration` page for more details.


**Basic configuration**


.. code-block:: yaml

    # Username for SSH connections, optional
    # If not specified, the current user will be used
    options:
      default_username: admin

    # Hosts to manage
    hosts:
    - name: dbhost1
      ip: dbhost1.example.com
      description: Database Server
    - name: web1
      ip: web1.example.com
      description: Frontend Web Server
    - name: fileserver
      ip: 192.168.0.28 # ip is fine too
      port: 2222       # Optional port if not 22
      username: alice  # This one has a special login
      # description is optional

.. admonition:: Note

    This assumes your private keys are loaded in your SSH agent.
    See :doc:`connections` for more details.


**Run Exosphere**

.. code-block:: console

    $ exosphere

At the exosphere prompt, you can run commands to manage your hosts.

**Discover Hosts**

.. code-block:: console

    exosphere> inventory discover

This will detect the platform and package manager for each host.
It only needs to be done once, or if something changes on the host.

**Refresh Updates**

.. code-block:: console

    exosphere> inventory refresh

This will retrieve the available updates and patches for each host.

**View Status and Host Details**

.. code-block:: console

    exosphere> inventory status
    exosphere> host show hostname

There you go! You are now set up with a *basic* Exosphere configuration and can aggregate your
updates all in one place.

Next Steps
----------

To go further, you can explore the various commands in the :doc:`cli` or start the full
:doc:`ui` for a more interactive experience:

.. code-block:: console

    $ exosphere ui start

.. tip::
   
   For more advanced configuration options, authentication details, and troubleshooting,
   see the full :doc:`configuration` and :doc:`connections` documentation.

