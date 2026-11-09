"""An extractor that reads a bearer token from a form-encoded body."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override

from xtr_security_http._form_content_type import is_form_content_type

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["FormEncodedBodyExtractor"]

#: The one form encoding a bearer token is posted in: RFC 6750, Section 2.2,
#: names the urlencoded one, so a multipart form carries no token here.
_URLENCODED_FORM: Final = frozenset({"application/x-www-form-urlencoded"})

#: The method whose body may carry a form, exactly as it travels on the wire.
#: RFC 9110 spells method names in upper case and matching them is
#: case-sensitive; a request that spells it any other way is not a form post.
_FORM_METHOD = "POST"

#: The largest form body read, so a bearer token in a body cannot be a memory
#: exhaustion vector; a larger body yields no token.
_MAX_BODY_SIZE = 64 * 1024


@final
class FormEncodedBodyExtractor(AccessTokenExtractorInterface):
    """Reads a token from a form field of an ``x-www-form-urlencoded`` body.

    RFC 6750 allows a bearer token in a form body; this reads the
    ``access_token`` field of one, when the request carries that content type.
    The body is read as the message the request arrived as — the read
    materialises it and its parsed side — and the token is read out of the
    parsed form, so no form-parsing dependency is needed.

    Attributes:
        field_name: The form field the token is read from.
    """

    __slots__ = ("_field_name",)

    def __init__(self, field_name: str = "access_token") -> None:
        """Build the extractor for the ``field_name`` form field."""
        self._field_name = field_name

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the form body, or ``None`` when it is absent.

        Only a ``POST`` whose content type names the urlencoded form encoding
        is read — the one request a submitted form travels as, its media type
        weighed whole, so one that only starts like it is no form. The body is
        read before the parsed form is asked for, the order a served request
        needs: the reading materialises both, and the parsed side answers
        behind it. A body that turns out larger than the 64 KiB cap yields no
        token — the cap weighs the bytes that actually arrived, never what a
        header promised — and so does a form whose field carries anything
        other than one text value; an endpoint behind the firewall then
        challenges rather than failing on the oversize or malformed body.
        """
        if request.get_method() != _FORM_METHOD:
            return None
        if not is_form_content_type(
            request.get_header_line("Content-Type"), media_types=_URLENCODED_FORM
        ):
            return None
        body = request.get_body()
        if len(await body.get_contents()) > _MAX_BODY_SIZE:
            return None
        parsed = request.get_parsed_body()
        if not isinstance(parsed, Mapping):
            return None
        value = cast("Mapping[str, object]", parsed).get(self._field_name)
        return value if isinstance(value, str) else None
