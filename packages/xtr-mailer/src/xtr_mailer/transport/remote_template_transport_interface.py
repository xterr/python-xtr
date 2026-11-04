"""What a transport able to send an email rendered from a provider's template derives from."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["RemoteTemplateTransportInterface"]


@runtime_checkable
class RemoteTemplateTransportInterface(Protocol):
    """Sends a :class:`~xtr_mailer.RemoteTemplateEmail` by handing its template to the provider.

    A marker with no member: a transport has it only by deriving from it, and is asked so by
    its class's ancestry, never by ``isinstance`` — with nothing to look for, a structural check
    would find it on any object. Any other transport refuses an email whose body is left to a
    provider's template, rather than deliver the placeholder that stands for that body.
    """
