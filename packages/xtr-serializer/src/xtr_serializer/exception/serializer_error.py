"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["SerializerError"]


class SerializerError(Exception):
    """Something the serializer could not do — catch this to catch them all.

    Serialization happens at the edges of an application: a request body read
    in, a message written to a queue. One ``except`` there has to answer for
    anything that went wrong, and this is that one; a subclass tells one cause
    from another — data that does not fit its type, a format nothing reads, a
    class hierarchy registered wrongly.

    No error of this package repeats a value it was handed. What goes through a
    serializer is often what an application must keep out of its logs — a
    password, a token, a customer's address — so a message says where the
    problem is and which types were involved, never what the value was.
    """
