"""The shape of the form a user switch is asked through."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["ImpersonationForm"]


class ImpersonationForm(TypedDict):
    """The action and the hidden fields of a form triggering a user switch.

    Unlike the URLs, the form keeps the switch's parameters out of the
    address bar: they ride in hidden fields, so the form suits a switch
    restricted to ``POST`` requests. Render each field as a hidden input
    of a form posted to the action.

    Attributes:
        action: The path the form is posted to — the page the switch is
            asked at, or the dedicated path when the firewall has one.
        fields: The hidden fields, each mapped to the value it carries:
            the user to switch to, the page to come back to on a
            dedicated path, and the forgery token when the switch asks
            for one.
        csrf_field: The name of the field carrying the forgery token, for
            a template to mark for client-side scripts, or ``None`` when
            the form carries none.
    """

    action: str
    fields: dict[str, str]
    csrf_field: str | None
