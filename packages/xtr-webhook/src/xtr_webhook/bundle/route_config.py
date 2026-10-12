"""One webhook type's route: which parser reads it, and what verifies it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from xtr_webhook.client.request_parser_interface import RequestParserInterface

__all__ = ["RouteConfig"]


@final
@dataclass(frozen=True, slots=True)
class RouteConfig:
    """What the endpoint does with webhooks of one type.

    Attributes:
        parser: The class reading this type's webhooks, built by the container
            with its dependencies on the first webhook for it. ``None`` means
            the bundle's own configured
            :class:`~xtr_webhook.client.RequestParser`, which verifies the
            signature scheme the bundle's ``signature_format`` names.
        secret: What this type's webhooks are verified against. Pass it
            through the container's ``env("...")`` placeholder, never as a
            literal: a placeholder is read only when the endpoint is built,
            and no container report prints it. It must be set in production —
            with an empty value, depending on the parser, requests from any
            sender are accepted or every request is rejected. Kept out of the
            ``repr``.
    """

    parser: type[RequestParserInterface] | None = None
    secret: str = field(default="", repr=False)
