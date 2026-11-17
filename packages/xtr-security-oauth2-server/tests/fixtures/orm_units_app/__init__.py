"""An application holding nothing but the orm bundle, on the database a test points it at.

The stored managers open units of work of their own through the kernel's scope
factory; this is the kernel that hands one out, so each unit is a real one: its
session built as the bundle builds it, closed when the unit ends.
"""
