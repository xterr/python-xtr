"""An extractor that reads a bearer token from the Authorization header."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["HeaderAccessTokenExtractor"]


@final
class HeaderAccessTokenExtractor(AccessTokenExtractorInterface):
    """Reads a token from a request header, ``Authorization: Bearer <token>`` by default.

    The standard reading is the one the framework's own bearer dependency
    performs — the scheme word and the credentials parted by the first space,
    the scheme matched without regard to case — so a missing or malformed
    header reads as ``None`` and the firewall's entry point — not the
    framework — answers the challenge. A different header name or token type
    folds the extraction onto the raw header value instead, for a scheme that
    is not the standard bearer one.

    Attributes:
        header_name: The header the token is read from.
        token_type: The scheme word before the token (``"Bearer"`` by default).
    """

    __slots__ = ("_header_name", "_reads_standard_bearer", "_token_type")

    def __init__(
        self,
        header_name: str = "Authorization",
        token_type: str = "Bearer",  # noqa: S107 -- a scheme word, not a secret
    ) -> None:
        """Build the extractor for ``header_name`` carrying a ``token_type`` token."""
        self._header_name = header_name
        self._token_type = token_type
        self._reads_standard_bearer = (
            header_name.lower() == "authorization" and token_type.lower() == "bearer"
        )

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the header, or ``None`` when it is absent or malformed."""
        header = request.get_header_line(self._header_name)
        if header == "":
            return None
        if self._reads_standard_bearer:
            scheme, _, credentials = header.partition(" ")
            if scheme == "" or credentials == "" or scheme.lower() != "bearer":
                return None
            return credentials
        return self._read_typed(header)

    def _read_typed(self, header: str) -> str | None:
        """Read a token off a non-standard header, honouring the configured type word."""
        if self._token_type == "":
            return header
        prefix = f"{self._token_type} "
        if header.startswith(prefix):
            return header[len(prefix) :]
        return None
