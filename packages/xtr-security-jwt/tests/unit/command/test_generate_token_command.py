"""``jwt:generate-token`` mints a token for a user loaded through a provider."""

from __future__ import annotations

import io

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_console import ConsoleStyle
from xtr_dependency_injection import ServiceLocator
from xtr_security_core.exception import UserNotFoundError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from tests.support.fakes import PlainUserProvider, RecordingDispatcher, provider_locator
from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.command.generate_token_command import GenerateTokenCommand
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

pytestmark = pytest.mark.anyio


def _style() -> tuple[ConsoleStyle, io.StringIO]:
    output = io.StringIO()
    style = ConsoleStyle(output, io.StringIO(), width=200, decorated=False, interactive=False)
    return style, output


def _manager() -> JwtManager:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        3600,
        0,
        MockClock("2024-01-01 00:00:00"),
    )
    return JwtManager(
        DefaultJwtEncoder(provider),
        RecordingDispatcher(),
        "username",
        issuer="https://jwt.test",
    )


def _locator(
    providers: dict[str, UserProviderInterface],
) -> ServiceLocator[UserProviderInterface]:
    return provider_locator(providers)


async def test_it_mints_a_token_for_the_only_provider() -> None:
    style, output = _style()
    providers = _locator({"users": PlainUserProvider(InMemoryUser("ada", roles=["ROLE_USER"]))})

    code = await GenerateTokenCommand()(style, _manager(), providers, "ada")

    assert code == 0
    assert output.getvalue().count(".") >= 2


async def test_it_needs_a_provider_name_when_several_are_configured() -> None:
    style, output = _style()
    providers = _locator(
        {
            "a": PlainUserProvider(InMemoryUser("ada")),
            "b": PlainUserProvider(InMemoryUser("ada")),
        },
    )

    code = await GenerateTokenCommand()(style, _manager(), providers, "ada")

    assert code == 1
    assert "--provider" in output.getvalue()


async def test_it_uses_the_named_provider() -> None:
    style, _ = _style()
    providers = _locator(
        {
            "a": PlainUserProvider(InMemoryUser("ada")),
            "b": PlainUserProvider(InMemoryUser("ada")),
        },
    )

    code = await GenerateTokenCommand()(style, _manager(), providers, "ada", provider="b")

    assert code == 0


async def test_an_unknown_provider_name_fails() -> None:
    style, output = _style()
    providers = _locator({"a": PlainUserProvider(InMemoryUser("ada"))})

    code = await GenerateTokenCommand()(style, _manager(), providers, "ada", provider="missing")

    assert code == 1
    assert "missing" in output.getvalue()


async def test_no_provider_configured_fails() -> None:
    style, output = _style()

    code = await GenerateTokenCommand()(style, _manager(), _locator({}), "ada")

    assert code == 1
    assert "No user provider" in output.getvalue()


class _MissingProvider(UserProviderInterface):
    """A provider that never finds a user."""

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        raise UserNotFoundError(identifier)

    @override
    def supports_class(self, user_class: type) -> bool:
        return issubclass(user_class, InMemoryUser)


async def test_a_user_that_cannot_be_loaded_fails() -> None:
    style, output = _style()
    providers = _locator({"users": _MissingProvider()})

    code = await GenerateTokenCommand()(style, _manager(), providers, "ghost")

    assert code == 1
    assert "ghost" in output.getvalue()
