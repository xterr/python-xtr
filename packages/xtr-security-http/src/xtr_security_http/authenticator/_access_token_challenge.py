"""Rendering the access-token authenticator's ``WWW-Authenticate`` challenge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_http._challenge import quote_auth_param

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.access_token.sender_constraint_interface import (
        SenderConstraintInterface,
    )

__all__ = ["access_token_challenge", "render_access_token_challenge", "resource_metadata_value"]


def render_access_token_challenge(
    scheme: str,
    parameters: Mapping[str, str],
    data: Mapping[str, str | None],
) -> str:
    """Render one challenge: ``scheme`` first, then every named value it carries.

    The sender constraint's ``parameters`` override the authenticator's own
    ``data`` — a constraint knows what a client needs to come back with, so
    its word wins over the generic spelling. A value that is ``None`` or
    empty is left out: a challenge names what it has to say, and RFC 6750
    Section 3 asks that a request lacking any authentication information be
    told no error code at all.
    """
    values = {**data, **parameters}
    parts = [
        f"{name}={quote_auth_param(value)}"
        for name, value in values.items()
        if value is not None and value != ""
    ]
    return scheme + (" " + ", ".join(parts) if parts else "")


def resource_metadata_value(
    request: ServerRequestInterface,
    resource_metadata_uri: str | None,
) -> str | None:
    """Answer the protected-resource metadata address the challenge names.

    A configured address is named as it is; one written as a path — opening
    with a slash — is resolved against the request's own scheme, authority
    and host, the way the client reached this resource, and the request's
    own query and fragment are left behind: the metadata document has its
    own address, not the asked-for one's.
    """
    if resource_metadata_uri is None:
        return None
    if not resource_metadata_uri.startswith("/"):
        return resource_metadata_uri
    return str(
        request.get_uri().with_path(resource_metadata_uri).with_query("").with_fragment(""),
    )


def access_token_challenge(  # noqa: PLR0913 -- one challenge, every input it is rendered from, gathered where the authenticator's state meets the request
    request: ServerRequestInterface,
    *,
    realm: str | None,
    resource_metadata_uri: str | None,
    sender_constraint: SenderConstraintInterface | None,
    error_code: str | None,
    error_description: str | None,
    error: AuthenticationError | None,
) -> str:
    """Build the ``WWW-Authenticate`` header the access-token authenticator challenges with.

    The scheme and the extra parameters come from the sender constraint
    when one is configured — a firewall accepting sender-constrained tokens
    challenges with the scheme they are presented under — and the
    constraint's parameters override the ones built here.
    """
    scheme: str = "Bearer"
    parameters: Mapping[str, str] = {}
    if sender_constraint is not None:
        scheme, parameters = sender_constraint.get_challenge(error)
    return render_access_token_challenge(
        scheme,
        parameters,
        {
            "realm": realm,
            "error": error_code,
            "error_description": error_description,
            "resource_metadata": resource_metadata_value(request, resource_metadata_uri),
        },
    )
