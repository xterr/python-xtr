"""An email the mail provider renders from a template hosted on its side."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_mime import Email, LogicError, TextPart

from .remote_template import RemoteTemplate

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_mime import AbstractPart, Headers

__all__ = ["RemoteTemplateEmail"]


class RemoteTemplateEmail(Email):
    """An email whose body the mail provider renders from one of its templates.

    Only a transport able to hand the template over sends it; any other refuses it, rather
    than deliver the placeholder that stands for the body here. With no template set it is
    an ordinary email.
    """

    def __init__(
        self,
        headers: Headers | None = None,
        body: AbstractPart | None = None,
        *,
        clock: ClockInterface | None = None,
    ) -> None:
        """Start as an ordinary email, with no template."""
        super().__init__(headers, body, clock=clock)
        self._template: RemoteTemplate | None = None

    def template(self, template: str | None, variables: Mapping[str, object] | None = None) -> Self:
        """Render the email from the provider's ``template`` with ``variables``; ``None`` stops."""
        self._template = None if template is None else RemoteTemplate(template, variables)
        return self

    def get_remote_template(self) -> RemoteTemplate | None:
        """Return the template, ``None`` unless set."""
        return self._template

    @override
    def get_body(self) -> AbstractPart:
        """Return a text part naming the template when one is set, else the email's body.

        Raises:
            LogicError: There is no template, no body set, no text, no HTML and no attachment.
            InvalidArgumentError: The HTML body is bytes in a charset Python does not know.
        """
        if self._template is None:
            return super().get_body()
        return TextPart(
            "This email is rendered by the mail provider from its "
            f'"{self._template.get_reference()}" template.'
        )

    @override
    def _ensure_body_valid(self) -> None:
        """Refuse a text or HTML body next to a template, which would never be shown.

        Raises:
            LogicError: There is a template and a text or HTML body, or neither a template nor
                anything to send.
        """
        if self._template is None:
            super()._ensure_body_valid()
        elif self.get_text_body() is not None or self.get_html_body() is not None:
            raise LogicError(
                "An email using a remote template cannot have a text or an HTML part; its body is "
                "rendered by the mail provider."
            )
