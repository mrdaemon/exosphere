Reporting and JSON Export
=========================

Exosphere includes a comprehensive reporting system that allows you to generate
detailed reports of your inventory status and system updates in multiple formats.

A highlight of the reporting system is that **it does not require any connectivity
or live access to hosts** and operates entirely from the Cache.

This means you can absolutely schedule reports or json to be exported on a schedule
from a different context where your ssh agent is not available.

All that is required is read access to the exosphere cache database.
For more details on that file, see :doc:`cachefile`.


Available Formats
-----------------

Below are examples of each output format to help you choose the right one for your needs.

.. _report-samples:

.. tabs::

    .. tab:: HTML Report

        Styled with a visually appealing design, entirely self-contained in a
        single file. Suitable for reading or printing. Offers an optional quick
        navigation box to jump between hosts.

        Recommended for most uses.

        .. figure:: _static/reporting_sample.png
            :alt: Sample HTML Report
            :align: center

            Partial screenshot of the html report, without navigation

        📁 **Sample Reports:**
      
        - :download:`Full Report <_static/reports/full.html>` - Complete inventory with all hosts
        - :download:`No Navigation <_static/reports/full-no-navigation.html>` - Without quick navigation menu
        - :download:`Filtered Report <_static/reports/filtered.html>` - Specific hosts selection
        - :download:`Security Updates Only <_static/reports/securityonly.html>` - Only security-related updates
        - :download:`Updates Only <_static/reports/updatesonly.html>` - Only hosts with available updates

    .. tab:: Plain Text

        Useful for quick overviews or for environments where rich text is not 
        supported. If you want a cron job that sends an email, don't worry, we got you.

        .. literalinclude:: ../../examples/reports/full.txt
            :language: text
            :lines: 1-30
            :caption: Plain Text Report Sample (partial)

        📁 **Sample Reports:**
        
        - :download:`Full Report <_static/reports/full.txt>` - Complete inventory, text format
        - :download:`Filtered Report <_static/reports/filtered.txt>` - Selected hosts only
        - :download:`Updates Only <_static/reports/updatesonly.txt>` - Hosts with updates available
        - :download:`Security Updates Only <_static/reports/securityonly.txt>` - Security updates only

    .. tab:: Markdown

        Made available mostly as a lightweight intermediate format, since they can be 
        rendered to a variety of other formats while providing support for tables.
        They can also be fed directly into any other tool that supports markdown.

        .. literalinclude:: ../../examples/reports/full.md
            :language: markdown
            :lines: 1-25
            :caption: Markdown Report Sample (header and first host info)

        📁 **Sample Reports:**
        
        - :download:`Full Report <_static/reports/full.md>` - Complete inventory, markdown format
        - :download:`Filtered Report <_static/reports/filtered.md>` - Selected hosts only
        - :download:`Updates Only <_static/reports/updatesonly.md>` - Hosts with updates available
        - :download:`Security Updates Only <_static/reports/securityonly.md>` - Security updates only 

    .. tab:: JSON Export
        
        Available for integration with other tools, implementation of which is left 
        as an exercise for the reader. It is also useful for displaying the raw internal
        state of the inventory and hosts.

        The downloadable examples below should give you a good idea of the structure.

        For more details on the JSON schema, see the :ref:`json-schema` section below.

        📁 **Sample Reports:**
        
        - :download:`Full Report <_static/reports/full.json>` - Complete JSON inventory
        - :download:`Security Updates Only <_static/reports/securityonly.json>` - Security updates in JSON
        - :download:`Updates Only <_static/reports/updatesonly.json>` - Available updates only
        - :download:`Filtered Report <_static/reports/filtered.json>` - Selected hosts as JSON


Basic Usage
-----------

The simplest way to generate a report is:

.. code-block:: shell

    $ exosphere report generate

This will output a plain text report to your terminal showing all hosts and their
update status.

The ``--format/-f`` option controls the output format, and accepts any of ``text``,
``html``, ``markdown``, or ``json``. 

**Save to File**

You can save the report to a file with ``--output/-o``:

.. code-block:: shell

    $ exosphere report generate --format html --output systems-report.html

**Displaying Specific Hosts**

Which hosts are included in the report can be controlled by specifying them as
arguments. For example, to generate a JSON report for just three hosts:

.. code-block:: shell

    $ exosphere report generate --format json web1 web2 database

**Updates Available Only**

The report can filtered to only show hosts with updates available using
``--updates-only``:

.. code-block:: shell

    $ exosphere report generate --updates-only --format html --output updates.html

**Security Updates Only**

To exclusively select security updates, use ``--security-updates-only``:

.. code-block:: shell

    $ exosphere report generate --security-updates-only

Advanced Options
----------------

**File Output with Preview**

    Use ``--tee`` to show the report in the terminal while also saving it
    to a file:

    .. code-block:: shell

        $ exosphere report generate --format html --output report.html --tee

**Quiet Mode**

    Suppress informational messages with ``--quiet``. Can be helpful in
    the context of scripts or cron jobs.

    .. code-block:: shell

        $ exosphere report generate --format json --quiet --output daily-report.json

**HTML Navigation**

    You can opt out of the quick navigation menu in HTML reports with
    ``--no-navigation``:

    .. code-block:: shell

        $ exosphere report generate --format html --no-navigation -o report.html

Report Content
--------------

All reports include:

- **Host Information**: Name, IP address, operating system details
- **Update Summary**: Total updates available, security updates count
- **Update Details**: Package names, versions, and security status
- **Metadata**: Report generation time and scope information

The presentation and formatting varies by format, but the core information
remains consistent across all output types.

.. tip::

    For detailed information about all available options and flags, 
    see :doc:`command_reference` or run ``exosphere report generate --help``.

.. _json-schema:

JSON Schema Details
-------------------

The JSON output format provides a structured representation of the inventory
and update information, making it suitable for programmatic consumption.

If you want to have a Discord bot that reports updates, or feed your event queue
for your astoundingly complex MQTT Doorbell Over Zigbee that also brews coffee,
this should enable you to do so.

JSON Schema
^^^^^^^^^^^

The JSON output follows a well-defined schema for consistency and integration purposes.
The schema is available in the source tree as ``exosphere/schema/host-report.schema.json``,
but is also made available here, corresponding to the version this documentation is built
for:

:download:`host-report.schema.json <_static/host-report.schema.json>` as of |CurrentVersionTag| 

Structure Overview
^^^^^^^^^^^^^^^^^^

The report consists of an array of host objects. When generated via the CLI, the hosts
will be pre-filtered to only include hosts that have been discovered, are supported,
and have a valid :doc:`package manager provider <providers>` assigned to them.

.. tip::

    Unless you are directly using the Python API (see :doc:`api/reporting`)
    to generate reports, you **can** safely assume that all the hosts in the
    report have been discovered, and **will not** have `null` values anywhere
    other than ``last_refresh`` (if the host has never been refreshed).


.. jsonschema-doc:: src/exosphere/schema/host-report.schema.json
   :section: definitions.host
   :title: Host Object Properties

.. admonition:: Note

    The ``description`` field will be omitted entirely if no description
    was provided for the host in the configuration.

Each host's ``updates`` array contains update objects with the following structure.

.. jsonschema-doc:: src/exosphere/schema/host-report.schema.json
   :section: definitions.update
   :title: Update Object Properties

.. admonition:: Note

    The ``current_version`` field may be ``null`` whenever the package is a new
    dependency. Interfaces in the Exosphere API usually translate this to the
    string `(NEW)`, but the raw JSON will have ``null`` in these cases.

.. literalinclude:: ../../examples/sample-report.json
   :language: json
   :caption: Example JSON report structure

More examples are available in the :ref:`Sample Reports <report-samples>`
section above.

Integration Examples
--------------------

Here are some concrete but deeply uncreative examples of how the reporting
feature can be used in practice.

If you make a cool thing, please `let us know`_ via a github issue!
We'll happily showcase it here.

**Email text report about security updates**

.. code-block:: shell

    #!/bin/bash
    exosphere report generate --updates-only --quiet \
    | mail -s "System Updates Available" bigadmin@example.com

**JSON Processing with jq**

.. code-block:: shell

    # Count hosts with security updates
    exosphere report generate --format json --security-updates-only | jq 'length'
    
    # Extract just host names and update counts
    exosphere report generate --format json | jq '.[] | {name, updates: .updates | length}'
    
    # The same but only hosts that have updates
    exosphere report generate --format json \
    | jq '.[] | select(.updates | length > 0) | {name, updates: .updates | length}'

.. _let us know: https://github.com/mrdaemon/exosphere/issues/new/choose
