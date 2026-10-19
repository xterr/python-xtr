"""The login-link handler: links signed by the core hasher, storing nothing."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final
from urllib.parse import urlencode, urlsplit

from typing_extensions import override
from xtr_security_core.exception import (
    ExpiredSignatureError,
    InvalidArgumentError,
    InvalidSignatureError,
    UserNotFoundError,
)

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.exception import ExpiredLoginLinkError, InvalidLoginLinkError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._clock import system_now
from ._presented_link import (
    PARAMETER_NAME,
    extra_parameters_of,
    required_parameter_of,
)
from .login_link_details import LoginLinkDetails
from .login_link_handler_interface import LoginLinkHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.signature.signature_hasher import SignatureHasher
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["LoginLinkHandler"]

#: The names the link's own reading uses; an extra parameter may not take one.
_RESERVED_PARAMETERS: Final = frozenset(("user", "expires", "hash", "hash_parameters"))

#: The options every handler carries, and their defaults. The lifetime is ten
#: minutes, the moment a link asks to be followed within; the path is where
#: every minted link leads — the one option with no default to fall back on.
_DEFAULT_OPTIONS: Final[Mapping[str, object]] = {"path": None, "lifetime": 600}


def _plain_path(path: str, request: ServerRequestInterface | None) -> str:
    """Return ``path`` as it is: the URI of a path is the path.

    The default URI builder. A ``Location`` header may carry a path, and
    the framework resolves it against the request's own host; an
    application that wants absolute links injects a builder that writes
    them, reading the request the link is generated against.
    """
    del request
    return path


def _is_absolute_url(path: str) -> bool:
    """Tell whether ``path`` already is an absolute URL."""
    split = urlsplit(path)
    return split.scheme != "" and split.netloc != ""


def _text_of(value: str | bool | float) -> str:
    """Render ``value`` as the query text the hash also reads it as.

    The hash covers the value the caller passed — a flag, a number — and
    the query carries its text; both must render the same, or a link
    would stop verifying the moment it was followed.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _as_login_link_message(error: Exception) -> str:
    """Rewrite a signature error's message as the login link's own.

    The core hasher says what it checked — a signature; the link's
    reader asked about a login link, so that is the word the refusal
    carries, the core's own message reworded rather than paraphrased.
    """
    message = re.sub("signature", "login link", str(error), flags=re.IGNORECASE)
    return message[:1].upper() + message[1:]


@final
class LoginLinkHandler(LoginLinkHandlerInterface):
    """Signs links with the core hasher, and checks the links presented back.

    A link is stateless: nothing is stored, and the link vouches for
    itself by a hash the core signature hasher computes over the user,
    the expiry and the link's extra parameters — checked against the
    identifier before the user is loaded, then against the loaded user's
    own covered fields, so a changed password retires every link issued
    before it. Which is also the limit: a single link cannot be revoked
    alone, only every link of the user, by changing what the signature
    covers.

    The link's URL is the configured path with the signed parameters as
    its query string. The URI the path becomes is written by the
    injected URI builder — the path itself by default — and the builder
    also receives the request the link is generated against, when there
    is one: the translation of building the link for that request's own
    address. This stack has no routing component to resolve a route name
    by, so the option is a literal path and a route name is refused.
    """

    __slots__ = (
        "_clock",
        "_lifetime",
        "_path",
        "_signature_hasher",
        "_uri_builder",
        "_user_provider",
    )

    def __init__(
        self,
        user_provider: UserProviderInterface,
        signature_hasher: SignatureHasher,
        options: Mapping[str, object] | None = None,
        uri_builder: Callable[[str, ServerRequestInterface | None], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Record the provider, the hasher, the options, the builder and the clock.

        Args:
            user_provider: Loads the user a presented link names, after
                the hash has proved the link sound.
            signature_hasher: Signs the links this handler mints and
                checks the ones it is handed.
            options: The link's shape, merged over the defaults —
                ``lifetime``, and ``path``, the literal path every minted
                link leads to, required.
            uri_builder: Writes the URI a path becomes, receiving the
                request the link is generated against when there is one;
                the path itself while ``None``.
            clock: Reads the current instant, for the moment each new
                link counts until; the system clock when ``None``.

        Raises:
            InvalidArgumentError: When ``options`` carries no ``path``, or
                names where a link leads by a route name.
        """
        merged = {**_DEFAULT_OPTIONS, **(options or {})}
        if "route_name" in merged:
            raise InvalidArgumentError(
                'The "route_name" option is not supported: this stack has no routing '
                'component to resolve one by; configure the literal "path" the link '
                "points at.",
            )
        path = merged["path"]
        if not isinstance(path, str) or not path:
            raise InvalidArgumentError(
                "The login-link handler requires a path option naming where the minted links lead.",
            )
        lifetime = merged["lifetime"]
        self._user_provider = user_provider
        self._signature_hasher = signature_hasher
        self._path = path
        self._lifetime = lifetime if isinstance(lifetime, int) else int(str(lifetime))
        self._uri_builder = _plain_path if uri_builder is None else uri_builder
        self._clock = clock if clock is not None else system_now

    @override
    async def create_login_link(
        self,
        user: UserInterface,
        request: ServerRequestInterface | None = None,
        lifetime: int | None = None,
        parameters: Mapping[str, str | bool | int | float] | None = None,
    ) -> LoginLinkDetails:
        """Sign a link for ``user``, until a lifetime from now.

        The extra parameters are sorted and their names listed in the
        link's ``hash_parameters`` — the list the reading back walks —
        and every one of them is covered by the hash, so a link cannot be
        re-pointed by editing what it carries. The names the link's own
        reading uses are reserved: ``user``, ``expires``, ``hash`` and
        ``hash_parameters``.

        Raises:
            InvalidArgumentError: When a parameter's name is malformed or
                reserved, or the configured path is a route name.
        """
        extra = dict(parameters or {})
        for name in extra:
            if not PARAMETER_NAME.match(name):
                raise InvalidArgumentError(
                    f'Login link parameter names must match "[A-Za-z0-9_.-]+", "{name}" given.',
                )
            if name in _RESERVED_PARAMETERS:
                raise InvalidArgumentError(f'Login link parameter name "{name}" is reserved.')
        expires = int(self._clock().timestamp()) + (lifetime or self._lifetime)
        if extra:
            extra = dict(sorted(extra.items()))
            extra["hash_parameters"] = ",".join(extra)
        hash_value = self._signature_hasher.compute_signature_hash(user, expires, extra)
        query: dict[str, str] = {name: _text_of(value) for name, value in extra.items()}
        query["user"] = user.get_user_identifier()
        query["expires"] = str(expires)
        query["hash"] = hash_value
        return LoginLinkDetails(self._with_query(self._uri(request), query), _moment(expires))

    @override
    async def consume_login_link(self, request: ServerRequestInterface) -> UserInterface:
        """Check the link ``request`` presents, and load the user it signs in.

        The link's parameters are read from the query string, or the body
        of a request that is not a ``GET``; the hash is checked against
        the identifier before the user is loaded — an unproven link must
        not cost a user lookup — then against the loaded user's own
        covered fields. The extra parameters the link carried are parked
        on the request's security state under the login-link parameters
        key, for the handlers that answer the login.

        Raises:
            InvalidLoginLinkError: When a parameter is missing or
                malformed, the hash verifies under no secret, or the
                provider knows no such user.
            ExpiredLoginLinkError: When the link's moment has passed.
        """
        user_identifier = required_parameter_of(request, "user", digits=False)
        hash_value = required_parameter_of(request, "hash", digits=False)
        expires = required_parameter_of(request, "expires", digits=True)
        parameters = extra_parameters_of(request)
        try:
            self._signature_hasher.accept_signature_hash(
                user_identifier,
                int(expires),
                hash_value,
                parameters,
            )
            user = await self._user_provider.load_user_by_identifier(user_identifier)
            self._signature_hasher.verify_signature_hash(user, int(expires), hash_value, parameters)
        except UserNotFoundError as error:
            raise InvalidLoginLinkError("User not found.") from error
        except ExpiredSignatureError as error:
            raise ExpiredLoginLinkError(_as_login_link_message(error)) from error
        except InvalidSignatureError as error:
            raise InvalidLoginLinkError(_as_login_link_message(error)) from error
        _ = parameters.pop("hash_parameters", None)
        security_state_of(state_bag_of(request)).attributes[
            SecurityRequestAttributes.LOGIN_LINK_PARAMETERS
        ] = parameters
        return user

    def _uri(self, request: ServerRequestInterface | None) -> str:
        """Return the configured path as the URI a minted link carries.

        An absolute URL is returned as it is; an absolute path goes
        through the URI builder — the path itself while none is
        injected. Anything else is a route name, which nothing here can
        resolve.

        Raises:
            InvalidArgumentError: When the configured path is neither an
                absolute path nor an absolute URL.
        """
        if _is_absolute_url(self._path):
            return self._path
        if not self._path.startswith("/"):
            raise InvalidArgumentError(
                f"The path {self._path!r} is not an absolute path; route names are "
                "not supported, only literal paths.",
            )
        return self._uri_builder(self._path, request)

    @staticmethod
    def _with_query(uri: str, query: dict[str, str]) -> str:
        """Return ``uri`` beside ``query`` as its query string."""
        if not query:
            return uri
        separator = "&" if "?" in uri else "?"
        return f"{uri}{separator}{urlencode(query)}"


def _moment(expires: int) -> datetime:
    """Return the Unix timestamp ``expires`` as the moment it names."""
    return datetime.fromtimestamp(expires, UTC)
