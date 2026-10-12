"""The stored client a deployment gets when it asks for no columns of its own."""

from __future__ import annotations

from .abstract_client import AbstractClient

__all__ = ["Client"]


class Client(AbstractClient):
    """A stored client, with exactly the registration the protocol needs.

    The default behind the ``client.classname`` setting, and the class the
    shipped table is mapped to. It adds nothing: a deployment that needs more
    — a tenant, an owner, a logo — extends
    :class:`~xtr_security_oauth2_server.model.abstract_client.AbstractClient`
    or this class and names the result in that setting.
    """
