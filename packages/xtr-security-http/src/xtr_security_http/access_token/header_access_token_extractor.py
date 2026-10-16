"""An extractor that reads a bearer token from the Authorization header."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.security import APIKeyHeader, HTTPBearer
from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
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

    __slots__ = ("_api_key", "_bearer", "_header_name", "_token_type")

    def __init__(
        self,
        header_name: str = "Authorization",
        token_type: str = "Bearer",  # noqa: S107 -- a scheme word, not a secret
    ) -> None:
        """Build the extractor for ``header_name`` carrying a ``token_type`` token."""
        self._header_name = header_name
        self._token_type = token_type
        standard = header_name.lower() == "authorization" and token_type.lower() == "bearer"
        self._bearer = (
            HTTPBearer(auto_error=False, bearerFormat="JWT", scheme_name="Bearer")
            if standard
            else None
        )
        self._api_key = (
            None
            if standard
            else APIKeyHeader(name=header_name, auto_error=False, scheme_name=header_name)
        )

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the header, or ``None`` when it is absent or malformed."""
        header = request.get_header_line(self._header_name)
        if header == "":
            return None
        if self._bearer is not None:
            scheme, _, credentials = header.partition(" ")
            if scheme == "" or credentials == "" or scheme.lower() != "bearer":
                return None
            return credentials
        return self._read_typed(header)

    @override
    def scheme(self) -> SecurityBase:
        """Return the bearer or API-key scheme this extractor reads and documents by."""
        return self._bearer if self._bearer is not None else self._require_api_key()

    def _read_typed(self, header: str) -> str | None:
        """Read a token off a non-standard header, honouring the configured type word."""
        if self._token_type == "":
            return header
        prefix = f"{self._token_type} "
        if header.startswith(prefix):
            return header[len(prefix) :]
        return None

    def _require_api_key(self) -> APIKeyHeader:
        """Return the API-key scheme, asserting it was built."""
        assert self._api_key is not None  # noqa: S101 -- built whenever the bearer is not
        return self._api_key
