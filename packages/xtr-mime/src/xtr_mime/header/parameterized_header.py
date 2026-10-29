"""A header holding a value and ``name=value`` parameters, such as Content-Type."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Final, final

from typing_extensions import override

from xtr_mime._engine import Parameterized
from xtr_mime.exception import RfcComplianceError

from .unstructured_header import UnstructuredHeader

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ParameterizedHeader"]

# RFC 2231's token: printable ASCII but space and the tspecials.
_TOKEN: Final = re.compile(r"[\x21\x23-\x27\x2a\x2b\x2d\x2e\x30-\x39\x41-\x5a\x5e-\x7e]+")

# WHATWG HTML, form submission: a form-data name or filename has these three replaced, and
# nothing else escaped.
_FORM_DATA_ESCAPES: Final = str.maketrans({'"': "%22", "\r": "%0D", "\n": "%0A"})


@final
class ParameterizedHeader(UnstructuredHeader):
    """A header written ``value; name="value"``, as Content-Type and Content-Disposition are.

    A parameter that is not ASCII, or too long for a line, is written in RFC 2231 form by the
    engine. A parameter set to ``None`` is kept but not written. In a ``form-data``
    Content-Disposition, ``name`` and ``filename`` get the escaping a browser applies.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_parameters",)

    def __init__(
        self, name: str, value: str, parameters: Mapping[str, str | None] | None = None
    ) -> None:
        """Keep ``name``, ``value`` and ``parameters``.

        Raises:
            RfcComplianceError: ``name`` is not a header name, or a parameter name is not a
                token.
        """
        super().__init__(name, value)
        self._parameters: dict[str, str | None] = {}
        if parameters is not None:
            self.set_parameters(parameters)

    def set_parameter(self, parameter: str, value: str | None) -> None:
        """Set one parameter, replacing it if it is there; ``None`` keeps it unwritten.

        Raises:
            RfcComplianceError: ``parameter`` is not a token.
        """
        self.set_parameters({**self._parameters, parameter: value})

    def get_parameter(self, parameter: str) -> str:
        """Return a parameter's value, empty when it is not set or set to ``None``."""
        return self._parameters.get(parameter) or ""

    def set_parameters(self, parameters: Mapping[str, str | None]) -> None:
        """Replace every parameter.

        Raises:
            RfcComplianceError: A parameter name is not a token; the parameters are then left
                as they were.
        """
        for parameter in parameters:
            if not _TOKEN.fullmatch(parameter):
                raise RfcComplianceError(
                    f'The parameter name "{parameter}" contains non-token characters.'
                )
        self._parameters = dict(parameters)

    def get_parameters(self) -> dict[str, str | None]:
        """Return the parameters, in order."""
        return dict(self._parameters)

    @override
    def _engine_value(self) -> Parameterized:
        written = {
            parameter: self._escape(parameter, value)
            for parameter, value in self._parameters.items()
            if value is not None
        }
        return Parameterized(self.get_value(), written)

    def _escape(self, parameter: str, value: str) -> str:
        is_form_data = (
            self.get_value() == "form-data" and self.get_name().lower() == "content-disposition"
        )
        if is_form_data and parameter in {"name", "filename"}:
            return value.translate(_FORM_DATA_ESCAPES)
        return value
