Package Manager Provider API
============================

This document provides an overview of the API used internally by Exosphere
to implement package manager providers.

A package manager provider is a Python class that implements the low level
API for a specific package manager. It is generally responsible for
connecting to the host, querying available package updates, parsing that list
and returning Update objects that can be used to populate state.

There is currently build-in support for the following package managers:

* `apt` (Debian, Ubuntu).
* `dnf` (Fedora, RHEL, CentOS).
* `yum` (RHEL, CentOS).
* `pkg` (FreeBSD).

.. automodule:: exosphere.providers.api
   :members:
   :undoc-members:
   :show-inheritance: