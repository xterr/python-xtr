"""``oauth2-server:create-client``: register a client and show its secret once."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Annotated, Final, final

import anyio.to_thread
from xtr_console import Argument, ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_dependency_injection import Target
from xtr_password_hasher import (
    PasswordHasherInterface,  # noqa: TC002 — container hydrates this constructor at runtime
)
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server._service_qualifier import SERVICE_QUALIFIER
from xtr_security_oauth2_server.exception.client_already_registered_error import (
    ClientAlreadyRegisteredError,
)
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.model.abstract_client import (
    AbstractClient,  # noqa: TC001 — container hydrates this constructor at runtime
)
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

from ._registry import OAUTH2_SERVER_COMMANDS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["CreateClientCommand"]

#: How many random bytes a secret nobody chose is made of. Shown as hex, so a
#: minted secret is twice this many characters.
_SECRET_BYTES: Final = 32

#: How many random bytes an identifier nobody chose is made of.
_IDENTIFIER_BYTES: Final = 16

#: What stands in the secret column for a client that holds none.
_PUBLIC: Final = "(public)"


@as_command("oauth2-server:create-client", registry=OAUTH2_SERVER_COMMANDS)
@final
class CreateClientCommand:
    """Registers a client, and shows the one plaintext of its secret there will be.

    What is stored is the *hash* of the secret, made with this package's own
    password hasher — so the secret itself exists only in the table this prints
    and in whatever the operator copies it into. Nothing can show it again: a
    client that lost its secret is given a new one, it is not reminded of the
    old one.

    A client is confidential unless ``--public`` says otherwise, and a public
    one holds no secret at all, so naming both is refused rather than quietly
    dropping one of them.

    An identifier already registered is refused rather than registered over:
    whatever the store would make of a second registration under one — replace
    the client, or refuse the write — the client known by that identifier
    would be left authenticating with a secret nobody was shown.
    """

    __slots__ = ("_client_class", "_client_manager", "_password_hasher")

    def __init__(
        self,
        client_manager: ClientManagerInterface,
        password_hasher: Annotated[PasswordHasherInterface, Target(SERVICE_QUALIFIER)],
        client_class: type[AbstractClient],
    ) -> None:
        """Register clients of ``client_class`` through ``client_manager``.

        Args:
            client_manager: Where the registration is written.
            password_hasher: What the secret is hashed with before it is
                written; this package's own, never the one an application
                hashes its users' passwords with.
            client_class: The class a registration is, which the deployment
                chose under ``client.classname``.
        """
        self._client_manager = client_manager
        self._password_hasher = password_hasher
        self._client_class = client_class

    async def __call__(  # noqa: PLR0913 — one registration's worth of fields
        self,
        io: ConsoleStyle,
        name: Annotated[str, Argument(help="What this client is called.")],
        identifier: Annotated[
            str | None,
            Argument(help="What this client is called by; a random one when left out."),
        ] = None,
        secret: Annotated[
            str | None,
            Argument(help="The secret this client proves itself with; a random one when left out."),
        ] = None,
        *,
        redirect_uri: Annotated[
            list[str] | None,
            Option(help="A redirect URI this client may be sent back to. Repeat for several."),
        ] = None,
        grant_type: Annotated[
            list[str] | None,
            Option(help="A grant this client may use. Repeat for several; none allows every one."),
        ] = None,
        scope: Annotated[
            list[str] | None,
            Option(help="A scope this client may ask for. Repeat for several; none allows any."),
        ] = None,
        public: Annotated[
            bool,
            Option(help="Register a client that holds no secret."),
        ] = False,
        allow_plain_text_pkce: Annotated[
            bool,
            Option(help="Let this client send an unhashed code challenge."),
        ] = False,
    ) -> int:
        """Register a client, store the hash of its secret, and show the plaintext once."""
        try:
            plain = _plain_secret(secret, public=public)
            client = self._built(
                name,
                identifier,
                redirect_uri or [],
                grant_type or [],
                scope or [],
                allow_plain_text_pkce=allow_plain_text_pkce,
            )
            identifier = await self._registered(client, plain)
        except (ClientAlreadyRegisteredError, InvalidArgumentError) as error:
            io.error(escape(str(error)))

            return ExitCode.FAILURE
        io.success("New OAuth2 client created successfully.")
        io.table(
            ["Identifier", "Secret"],
            [[escape(identifier), escape(plain) if plain is not None else _PUBLIC]],
        )

        return ExitCode.SUCCESS

    async def _registered(self, client: ClientInterface, plain: str | None) -> str:
        """Store ``client`` under ``plain``'s hash, and return what it is known by.

        The identifier is read before the write: a stored client is committed
        as it is saved, which leaves the instance needing a reload before it
        answers again — and a reload is not something a printed table should
        cost.

        Raises:
            ClientAlreadyRegisteredError: When the identifier is one another
                client already holds — looked for here, and raised by the
                store itself when it is taken between the look and the write.
        """
        identifier = client.get_identifier()
        if await self._client_manager.find(identifier) is not None:
            raise ClientAlreadyRegisteredError(identifier)
        if plain is not None:
            client.set_secret(await anyio.to_thread.run_sync(self._password_hasher.hash, plain))
        await self._client_manager.save(client)

        return identifier

    def _built(  # noqa: PLR0913 — one registration's worth of fields
        self,
        name: str,
        identifier: str | None,
        redirect_uris: Sequence[str],
        grants: Sequence[str],
        scopes: Sequence[str],
        *,
        allow_plain_text_pkce: bool,
    ) -> ClientInterface:
        """Return the registration to store, its value objects checked as they are made.

        Built holding no secret at all, and given the hash of one afterwards:
        a registration never holds a plaintext secret, not even briefly, and
        nothing but the table this command prints ever sees one.

        Raises:
            InvalidArgumentError: When a redirect URI, a grant or a scope is
                not one, which the value objects refuse where they are made.
        """
        client = self._client_class(
            name,
            identifier or secrets.token_hex(_IDENTIFIER_BYTES),
            None,
        )
        _ = client.set_active(True)
        _ = client.set_allow_plain_text_pkce(allow_plain_text_pkce)
        _ = client.set_redirect_uris(*(RedirectUri(one) for one in redirect_uris))
        _ = client.set_grants(*(Grant(one) for one in grants))
        _ = client.set_scopes(*(Scope(one) for one in scopes))

        return client


def _plain_secret(secret: str | None, *, public: bool) -> str | None:
    """Return the secret to hash: the one given, a minted one, or none at all.

    Raises:
        InvalidArgumentError: When a public client was asked for with a
            secret, which it would have nothing to do with.
    """
    if public:
        if secret is not None:
            raise InvalidArgumentError("The client cannot have a secret and be public.")

        return None

    return secret or secrets.token_hex(_SECRET_BYTES)
