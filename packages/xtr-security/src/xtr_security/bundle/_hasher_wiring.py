"""The password-hasher wiring: the factory, the user hasher and the timing guard."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TYPE_CHECKING, Annotated, cast, final

from xtr_dependency_injection import Target, named_factory
from xtr_password_hasher import (
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    PasswordHasherInterface,
    UserPasswordHasher,
    UserPasswordHasherInterface,
)

from xtr_security.bundle._password_hasher_build import build_hasher
from xtr_security.bundle.password_hasher_configs import AutoHasherConfig, ServiceHasherConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_dependency_injection import ServiceConfigurator

    from xtr_security.bundle.password_hasher_configs import HasherConfig
    from xtr_security.bundle.security_config import SecurityConfig

__all__ = [
    "DUMMY_PASSWORD_HASHER_QUALIFIER",
    "register_hashers",
]

DUMMY_PASSWORD_HASHER_QUALIFIER = "security.dummy_password_hasher"  # noqa: S105 -- a service qualifier, not a secret
"""The qualifier the timing-guard dummy hasher is registered under.

The per-firewall credentials check burns a verify against this hasher for an
unknown user, so a bad username costs the same as a bad password. It is a
service of its own — not the user hasher — so a test can override it with a
counting hasher and prove the burn ran through the wired dispatcher.
"""


@final
class _ServiceHasher:
    """The type a hasher the application registered is collected under.

    A password hasher configured as a service is forwarded under this private
    type so the hasher factory can gather every one into a ``Mapping`` keyed by
    a qualifier of its own, without pulling the whole container in.
    """

    __slots__ = ()


def _qualified(service: type, qualifier: Hashable) -> object:
    """Return the injection annotation selecting ``service`` under ``qualifier``.

    Built at runtime from a configured type, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression; the
    container evaluates it as the marker it forms.
    """
    return Annotated[service, Target(qualifier)]  # ty: ignore[invalid-type-form] -- runtime marker


def register_hashers(services: ServiceConfigurator, config: SecurityConfig) -> None:
    """Register the password hasher factory and the user hasher from the config.

    Every hasher configured as a service is forwarded under :class:`_ServiceHasher`
    so the factory gathers them by injecting a ``Mapping``; the other hasher
    configurations the factory closes over and builds itself. The factory and the
    user hasher are registered under their interfaces so a service asks for either
    by type.
    """
    static_hashers: dict[type | str, HasherConfig] = {}
    service_entries: list[tuple[type | str, str]] = []
    for index, (key, hasher_config) in enumerate(config.password_hashers.items()):
        if isinstance(hasher_config, ServiceHasherConfig):
            qualifier = f"security_service_hasher_{index}"
            forward = _service_hasher_forward(hasher_config.service, hasher_config.qualifier)
            _ = services.set(named_factory(forward, qualifier), qualifier=qualifier)
            service_entries.append((key, qualifier))
        else:
            static_hashers[key] = hasher_config

    _ = services.set(_password_hasher_factory(static_hashers, tuple(service_entries)))
    services.alias(PasswordHasherFactoryInterface, PasswordHasherFactory)
    _ = services.set(_user_password_hasher)
    services.alias(UserPasswordHasherInterface, UserPasswordHasher)
    _ = services.set(
        _dummy_password_hasher(_default_hasher_config(config)),
        qualifier=DUMMY_PASSWORD_HASHER_QUALIFIER,
    )


def _default_hasher_config(config: SecurityConfig) -> HasherConfig:
    """Return the hasher config the dummy timing-guard hasher mirrors.

    The dummy burn must cost what a real verify costs, so it is built from the
    application's first configured hasher — the default the hash command hashes
    for too. A service hasher cannot be built without the container, and nothing
    configured falls back to the secure default, so either yields
    :class:`AutoHasherConfig`.

    The guard is only worth what the mirrored hasher costs: an application whose
    default is a plaintext hasher burns nothing, so a missing user still answers
    faster than a wrong password. That is the plaintext hasher's documented
    trade, not a defect here — an application that wants the guard configures a
    real hasher as its default.
    """
    for hasher_config in config.password_hashers.values():
        if isinstance(hasher_config, ServiceHasherConfig):
            break
        return hasher_config
    return AutoHasherConfig()


def _dummy_password_hasher(
    config: HasherConfig,
) -> Callable[[], PasswordHasherInterface]:
    """Return a factory building the timing-guard hasher from ``config``."""

    def dummy_password_hasher() -> PasswordHasherInterface:
        return build_hasher(config)

    return dummy_password_hasher


def _service_hasher_forward(
    service: type,
    qualifier: Hashable | None,
) -> Callable[..., Awaitable[_ServiceHasher]]:
    """Return a factory forwarding an application hasher service under :class:`_ServiceHasher`."""

    async def service_hasher(hasher: object) -> _ServiceHasher:
        return cast("_ServiceHasher", hasher)

    service_hasher.__annotations__ = {
        "hasher": _qualified(service, qualifier) if qualifier is not None else service,
        "return": _ServiceHasher,
    }
    return service_hasher


def _password_hasher_factory(
    static_hashers: Mapping[type | str, HasherConfig],
    service_entries: Sequence[tuple[type | str, str]],
) -> Callable[..., Awaitable[PasswordHasherFactory]]:
    """Return the factory building the :class:`PasswordHasherFactory` from the config.

    The static configurations are built into ready hashers here — the factory
    itself takes instances, not configuration — and the service hashers a
    container provides are gathered in beside them.
    """
    fixed = {key: build_hasher(config) for key, config in static_hashers.items()}

    async def password_hasher_factory(
        service_hashers: Mapping[Hashable, _ServiceHasher] | None = None,
    ) -> PasswordHasherFactory:
        resolved: dict[type | str, PasswordHasherInterface] = dict(fixed)
        if service_hashers is not None:
            for config_key, qualifier in service_entries:
                resolved[config_key] = cast(
                    "PasswordHasherInterface", cast("object", service_hashers[qualifier])
                )
        return PasswordHasherFactory(resolved)

    if service_entries:
        password_hasher_factory.__annotations__ = {
            "service_hashers": Mapping[Hashable, _ServiceHasher],
            "return": PasswordHasherFactory,
        }
    return password_hasher_factory


def _user_password_hasher(factory: PasswordHasherFactoryInterface) -> UserPasswordHasher:
    """Build the user password hasher over the configured factory."""
    return UserPasswordHasher(factory)
