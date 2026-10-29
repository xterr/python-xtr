"""The application's services, and everything without a type folder of its own.

Value objects, interfaces next to their implementations, decorators of other services, boot
and shutdown hooks, compiler passes, logging processors: one public class or function per
module, the module named after it. The kernel's scan finds every one.
"""

from __future__ import annotations

__all__: list[str] = []
