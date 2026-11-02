"""Class hierarchies carried through serialization, each value written with its class's name.

A base class declares its hierarchy with :func:`discriminator_map`, and each class under it the
name it is written under with :func:`discriminator_name`. A field declaring any class of the
hierarchy then holds a value of any of its named subclasses, and reads it back as that class.
"""

from __future__ import annotations

from .discriminator_map import discriminator_map
from .discriminator_name import discriminator_name

__all__ = ["discriminator_map", "discriminator_name"]
