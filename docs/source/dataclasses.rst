Data Classes
=============

The core objects used by Exosphere are mostly `Host` and `Update` objects.

`Host` is the high level object, providing functionality to interact with the host and
perform operations on it, such as discovery or refreshing package updates.

The only mandatory fields for a Host are defined by the `HostInfo` dataclass, listed below.

.. autoclass:: exosphere.data.HostInfo
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: exosphere.data.Update
   :members:
   :undoc-members:
   :show-inheritance:
