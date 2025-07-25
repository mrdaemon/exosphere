"""
Context module for Exosphere

Global context, variables and other shared state objects used
throughout the Exosphere application.
"""

from exosphere.inventory import Inventory

inventory: Inventory | None = None
confpath: str | None = None
