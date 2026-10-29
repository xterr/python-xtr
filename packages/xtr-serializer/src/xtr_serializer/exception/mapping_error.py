"""A class hierarchy was registered for serialization in a way that cannot work."""

from __future__ import annotations

from .logic_error import LogicError

__all__ = ["MappingError"]


class MappingError(LogicError):
    """A class hierarchy was registered for serialization in a way that cannot work.

    The names registered for the classes of a hierarchy are what lets written
    data say which class it came from, so they must be unambiguous: one name for
    two classes, a name on a class outside the hierarchy it is registered in, or
    a name written under a key that a field also uses would each make some value
    read back as the wrong class. Raised when the classes are registered, so the
    mistake shows when the module is imported rather than when the first value
    fails to come back.
    """
