Exosphere configuration
=======================

The configuration module in Exosphere is wildly flexible, allowing you
to essentially provide your configuration structure in any format you'd like.

At runtime, the effective, current configuration structure is accessible
through ``exosphere.app_config``, which will always contain, at the very least
the default values defined in the ``Configuration.DEFAULTS`` dict.

It is *deeply* inspired from the Flask configuration system, since good
things are good.

.. automodule:: exosphere.config

   .. autoclass:: Configuration
      :members:
      :undoc-members:
      :show-inheritance:
      :exclude-members: DEFAULTS

      .. autoattribute:: DEFAULTS
         :annotation: = {...}
