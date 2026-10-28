"""The shape of the form a logout is asked through."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["LogoutForm"]


class LogoutForm(TypedDict):
    """The action and the hidden fields of a form triggering a logout.

    Unlike the logout URLs, the form keeps the cross-site request forgery
    token out of the address bar: the token rides in a hidden field, so the
    form suits a logout restricted to ``POST`` requests. Render each field
    as a hidden input of a form posted to the action.

    Attributes:
        action: The path the form is posted to — the firewall's logout path.
        fields: The hidden fields, each mapped to the value it carries; the
            forgery token under its parameter name, when the firewall's
            logout asks for one.
        csrf_field: The name of the field carrying the forgery token, for a
            template to mark for client-side scripts, or ``None`` when the
            form carries none.
    """

    action: str
    fields: dict[str, str]
    csrf_field: str | None
