"""A header holding a value and ``name=value`` parameters, such as Content-Type."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Final, final

from typing_extensions import override

from xtr_mime._engine import Parameterized
from xtr_mime._error_text import escaped
from xtr_mime.exception import RfcComplianceError

from .unstructured_header import UnstructuredHeader

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ParameterizedHeader"]

# RFC 2231's token: printable ASCII but space and the tspecials.
_TOKEN: Final = re.compile(r"[\x21\x23-\x27\x2a\x2b\x2d\x2e\x30-\x39\x41-\x5a\x5e-\x7e]+")
# A value too long for a line is cut into RFC 2231 sections, each on a line of its own after
# the name, a section number, a charset and at least one character written as up to 12. A name
# this long leaves room for them on a folded line; a longer one may leave none, and the
# engine's folding then never ends.
_LONGEST_NAME: Final = 40


@final
class ParameterizedHeader(UnstructuredHeader):
    """A header written ``value; name="value"``, as Content-Type and Content-Disposition are.

    A parameter that is not ASCII, or too long for a line, is written in RFC 2231 form by the
    engine. A parameter set to ``None`` is kept but not written.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_parameters",)

    def __init__(
        self, name: str, value: str, parameters: Mapping[str, str | None] | None = None
    ) -> None:
        """Keep ``name``, ``value`` and ``parameters``.

        Raises:
            RfcComplianceError: ``name`` is not a header name, or a parameter name is not a
                token or is longer than 40 characters.
        """
        super().__init__(name, value)
        self._parameters: dict[str, str | None] = {}
        if parameters is not None:
            self.set_parameters(parameters)

    def set_parameter(self, parameter: str, value: str | None) -> None:
        """Set one parameter, replacing it if it is there; ``None`` keeps it unwritten.

        Raises:
            RfcComplianceError: ``parameter`` is not a token or is longer than 40 characters.
        """
        self.set_parameters({**self._parameters, parameter: value})

    def get_parameter(self, parameter: str) -> str:
        """Return a parameter's value, empty when it is not set or set to ``None``."""
        return self._parameters.get(parameter) or ""

    def set_parameters(self, parameters: Mapping[str, str | None]) -> None:
        """Replace every parameter.

        Raises:
            RfcComplianceError: A parameter name is not a token or is longer than 40
                characters; the parameters are then left as they were.
        """
        for parameter in parameters:
            if not _TOKEN.fullmatch(parameter):
                raise RfcComplianceError(
                    f'The parameter name "{escaped(parameter)}" contains non-token characters.'
                )
            if len(parameter) > _LONGEST_NAME:
                raise RfcComplianceError(
                    f"A parameter name must be at most {_LONGEST_NAME} characters long "
                    f"({len(parameter)} given)."
                )
        self._parameters = dict(parameters)

    def get_parameters(self) -> dict[str, str | None]:
        """Return the parameters, in order."""
        return dict(self._parameters)

    @override
    def _engine_value(self) -> Parameterized:
        written = {
            parameter: value for parameter, value in self._parameters.items() if value is not None
        }
        return Parameterized(self.get_value(), written)
