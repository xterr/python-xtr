"""A header holding free text, such as Subject."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from .abstract_header import AbstractHeader

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue

__all__ = ["UnstructuredHeader"]


class UnstructuredHeader(AbstractHeader):
    """A header whose body is text, written as it is or as encoded words when it is not ASCII.

    Open to subclassing: a header with a name and a meaning of its own but a text body —
    a tag, a piece of metadata — is one of these.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_value",)

    def __init__(self, name: str, value: str) -> None:
        """Keep ``name`` and the text ``value``.

        Raises:
            RfcComplianceError: ``name`` is not a header name.
        """
        super().__init__(name)
        self._value: str = value

    @override
    def set_body(self, body: object) -> None:
        """Replace the text.

        Raises:
            InvalidArgumentError: ``body`` is not a string.
        """
        if not isinstance(body, str):
            self._refuse_body("a string", body)
        self.set_value(body)

    @override
    def get_body(self) -> str:
        """Return the text, as given."""
        return self.get_value()

    def get_value(self) -> str:
        """Return the text, as given: not encoded."""
        return self._value

    def set_value(self, value: str) -> None:
        """Replace the text."""
        self._value = value

    @override
    def _engine_value(self) -> HeaderValue:
        return self._value
