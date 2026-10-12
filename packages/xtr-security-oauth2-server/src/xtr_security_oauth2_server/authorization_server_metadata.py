"""The document a client reads to find out what this server can do."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final
from urllib.parse import urlsplit

from typing_extensions import override

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["AuthorizationServerMetadata"]

#: The fields this document names an endpoint in, in the order they are
#: written. A deployment hands over the ones it actually serves, so a server
#: with no device flow and no introspection simply names neither.
ENDPOINT_FIELDS: Final[tuple[str, ...]] = (
    "authorization_endpoint",
    "token_endpoint",
    "jwks_uri",
    "revocation_endpoint",
    "introspection_endpoint",
    "device_authorization_endpoint",
)

#: How a client may authenticate to an endpoint that authenticates clients:
#: HTTP Basic, credentials in the form, and — for a public client, which holds
#: no secret — not at all.
CLIENT_AUTH_METHODS: Final[tuple[str, ...]] = (
    "client_secret_basic",
    "client_secret_post",
    "none",
)

#: Which authorization-response the grants that send a browser somewhere ask
#: for. A grant that is not here redirects nobody, so it contributes none.
_RESPONSE_TYPES: Final[Mapping[str, str]] = MappingProxyType(
    {"authorization_code": "code", "implicit": "token"},
)

#: The endpoints that authenticate the client calling them and therefore
#: publish how it may do so.
_AUTHENTICATING_ENDPOINTS: Final[tuple[str, ...]] = (
    "token_endpoint",
    "revocation_endpoint",
    "introspection_endpoint",
)

_NOTHING_MORE: Final[Mapping[str, object]] = MappingProxyType({})
_NO_ENDPOINTS: Final[Mapping[str, str]] = MappingProxyType({})


@final
@dataclass(frozen=True, repr=False, slots=True)
class AuthorizationServerMetadata:
    """What this server tells a client about itself, before any request is made.

    A client that has only the issuer's name needs to find out where to send
    people, where to exchange a code, which scopes exist and which proof-key
    methods are accepted. RFC 8414 is how it asks: one document, at a fixed
    place under the issuer, saying all of it.

    The document is built from what is actually turned on. An endpoint a
    deployment does not serve is simply absent, and so is a field there is
    nothing to say about — no scopes declared, no grant that redirects — rather
    than present and empty, because a client reads an absent field as "not
    supported" and an empty one as a server that could not make up its mind.
    The one exception is the set of response types, which RFC 8414 requires:
    a server running none says so with an empty list rather than by omission.

    An extension may contribute fields of its own, and they are merged under
    everything this server decides: a contributed ``issuer`` or
    ``token_endpoint`` cannot take over, because those are not an extension's
    to answer.

    Attributes:
        issuer: The origin this server is known by, which is also what its
            tokens claim. It must be an origin and nothing more, because the
            document lives at a fixed path under it.
        endpoints: Where each served endpoint is, keyed by the field it is
            named in — see :data:`ENDPOINT_FIELDS`.
        grants: The flows this server runs, by the name a request asks for.
        scopes: The scopes a client may ask for.
        code_challenge_methods: How a proof key may be derived.
        extra: Fields an extension contributes.
    """

    issuer: str
    endpoints: Mapping[str, str] = field(default=_NO_ENDPOINTS)
    grants: Sequence[str] = ()
    scopes: Sequence[str] = ()
    code_challenge_methods: Sequence[str] = ()
    extra: Mapping[str, object] = field(default=_NOTHING_MORE)

    def __post_init__(self) -> None:
        """Refuse an issuer that is not an origin, or an endpoint with no field.

        Raises:
            InvalidArgumentError: When the issuer carries a path, a query or a
                fragment, or names no scheme or no host; and when an endpoint
                is keyed by a field this document does not define.
        """
        _refuse_unless_an_origin(self.issuer)
        unknown = sorted(set(self.endpoints) - set(ENDPOINT_FIELDS))
        if unknown:
            raise InvalidArgumentError(
                f"This document has no field for the endpoints {unknown}; name an endpoint by "
                f"one of {list(ENDPOINT_FIELDS)}, or contribute it as an extra field.",
            )

    def to_dict(self) -> Mapping[str, object]:
        """Return the document as the JSON object a client reads."""
        document: dict[str, object] = {"issuer": self.issuer}
        for name in ENDPOINT_FIELDS:
            where = self.endpoints.get(name)
            if where is not None:
                document[name] = where
        if self.scopes:
            document["scopes_supported"] = list(self.scopes)
        document["response_types_supported"] = list(self._response_types())
        if self.grants:
            document["grant_types_supported"] = list(self.grants)
        for name in _AUTHENTICATING_ENDPOINTS:
            if name in self.endpoints:
                document[f"{name}_auth_methods_supported"] = list(CLIENT_AUTH_METHODS)
        if self.code_challenge_methods:
            document["code_challenge_methods_supported"] = list(self.code_challenge_methods)
        for name, value in self.extra.items():
            _ = document.setdefault(name, value)

        return document

    def _response_types(self) -> Sequence[str]:
        """Return the authorization responses the enabled grants ask for."""
        answered: list[str] = []
        for grant in self.grants:
            response_type = _RESPONSE_TYPES.get(grant)
            if response_type is not None and response_type not in answered:
                answered.append(response_type)

        return tuple(answered)

    @override
    def __repr__(self) -> str:
        """Name the issuer and which endpoints are served, not where they are."""
        return f"{type(self).__name__}(issuer={self.issuer!r}, endpoints={tuple(self.endpoints)!r})"


def _refuse_unless_an_origin(issuer: str) -> None:
    """Refuse ``issuer`` unless it is a scheme and a host and nothing more.

    The document lives at a fixed path under the issuer, so an issuer carrying
    a path of its own would put it somewhere a client would not look — and the
    ``iss`` every token claims has to be exactly this string.

    Raises:
        InvalidArgumentError: When the issuer is not an origin.
    """
    split = urlsplit(issuer)
    if (
        split.scheme == ""
        or split.netloc == ""
        or split.path != ""
        or split.query != ""
        or split.fragment != ""
    ):
        raise InvalidArgumentError(
            f"The issuer {issuer!r} is not an origin; name it as a scheme and a host with no "
            "path, query or fragment, such as 'https://authorization.example.com'.",
        )
