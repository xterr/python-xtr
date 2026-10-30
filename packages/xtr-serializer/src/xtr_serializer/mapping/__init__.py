"""The names of the classes of each hierarchy, and how a hierarchy is read and written.

A hierarchy is declared with the decorators of :mod:`xtr_serializer.decorator`;
:class:`ClassDiscriminatorMapping` tells which names a class of it reads.
"""

from __future__ import annotations

from .class_discriminator_mapping import ClassDiscriminatorMapping

__all__ = ["ClassDiscriminatorMapping"]
