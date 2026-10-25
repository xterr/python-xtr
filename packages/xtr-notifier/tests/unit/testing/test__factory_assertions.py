from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient

from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.testing import FactoryCases, assert_factory_cases
from xtr_notifier.transport import AbstractTransportFactory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.transport import Dsn


@final
class _ChatFactory(AbstractTransportFactory):
    """Serves ``chat://TOKEN@host?channel=...``."""

    @override
    def create(self, dsn: Dsn) -> FakeTransport:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "chat", self._get_supported_schemes())
        _ = self._get_user(dsn)
        return FakeTransport(f"{dsn.host}-{dsn.get_required_option('channel')}")

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("chat",)


def _factory() -> _ChatFactory:
    return _ChatFactory(MockHttpClient())


def test_it_passes_a_factory_that_does_what_its_cases_say() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_factory,
            supports=[(True, "chat://token@default"), (False, "other://token@default")],
            create=[("default-ops://local", "chat://token@default?channel=ops")],
            unsupported_scheme=[
                ("other://token@default", None),
                ("other://token@default", 'The "other" scheme is not supported; '),
            ],
            incomplete_dsn=[("chat://default?channel=ops", "User is not set.")],
            missing_required_option=[
                ("chat://token@default", 'The option "channel" is required but missing.')
            ],
        )
    )


def test_it_reports_every_case_a_factory_fails_at_once() -> None:
    cases = FactoryCases(
        create_factory=_factory,
        supports=[(False, "chat://token@default")],
        create=[("wrong://", "chat://token@default?channel=ops"), ("x", "chat://token@default")],
        unsupported_scheme=[("chat://token@default?channel=ops", None)],
        incomplete_dsn=[("chat://default?channel=ops", "Missing token.")],
        missing_required_option=[("chat://default", None)],
    )

    with pytest.raises(AssertionError) as caught:
        assert_factory_cases(cases)

    assert str(caught.value).splitlines() == [
        "The factory fails 6 case(s):",
        '- it supports "chat://token@default"',
        '- "chat://token@default?channel=ops" creates "default-ops://local", not "wrong://"',
        (
            '- "chat://token@default" raised MissingRequiredOptionError: '
            'The option "channel" is required but missing.'
        ),
        '- "chat://token@default?channel=ops" raised nothing, not UnsupportedSchemeError',
        (
            '- "chat://default?channel=ops" raised IncompleteDsnError: '
            'Invalid "chat://default" notifier DSN: User is not set., without "Missing token."'
        ),
        (
            '- "chat://default" raised IncompleteDsnError: '
            'Invalid "chat://default" notifier DSN: User is not set., '
            "not MissingRequiredOptionError"
        ),
    ]
