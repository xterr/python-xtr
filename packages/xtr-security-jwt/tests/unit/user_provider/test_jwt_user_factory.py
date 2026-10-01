"""The user-provider factory reports its contract and builds the stateless provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_security_jwt.bundle.jwt_user_provider_config import JwtUserProviderConfig
from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_provider import JwtUserProvider
from xtr_security_jwt.user_provider.jwt_user_factory import JwtUserFactory

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator


def test_it_names_the_jwt_key_and_the_config() -> None:
    factory = JwtUserFactory()

    assert factory.key == "jwt"
    assert factory.config_type is JwtUserProviderConfig


def test_the_provider_config_defaults_to_the_plain_jwt_user() -> None:
    assert JwtUserProviderConfig().user_class is JwtUser


def test_it_registers_a_provider_under_the_provider_name() -> None:
    factory = JwtUserFactory()
    recorder = _Recorder()

    key = factory.create(
        cast("ServiceConfigurator", cast("object", recorder)),
        cast("ContainerBuilder", object()),
        "jwt_users",
        JwtUserProviderConfig(),
    )

    assert key == (JwtUserProvider, "jwt_users")
    assert isinstance(recorder.instance_value, JwtUserProvider)
    assert recorder.qualifier == "jwt_users"


@final
class _Definition:
    def __init__(self, key: tuple[type, str | None]) -> None:
        self.key: tuple[type, str | None] = key


@final
class _Recorder:
    def __init__(self) -> None:
        self.instance_value: object = None
        self.qualifier: str | None = None

    def instance(self, obj: object, *, qualifier: str | None = None) -> _Definition:
        self.instance_value = obj
        self.qualifier = qualifier
        return _Definition((type(obj), qualifier))
