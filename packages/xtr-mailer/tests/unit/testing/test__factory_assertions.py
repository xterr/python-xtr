from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer.exception import UnsupportedSchemeError
from xtr_mailer.testing import PASSWORD, USER, FactoryCases, assert_factory_cases
from xtr_mailer.transport import AbstractTransportFactory, Dsn, NullTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

_KEY = "Dsn(scheme='key', host='default', port=None, options={})"
_OTHER = "Dsn(scheme='other', host='default', port=None, options={})"
_UNSUPPORTED = (
    'The "other" scheme is not supported; supported schemes for mailer "key" are: "key", "smtp".'
)


@final
class _KeyFactory(AbstractTransportFactory):
    """Serves ``key://USER@host`` and ``smtp://USER@host``; a ``name`` option names its transport.

    A DSN without a user is incomplete.
    """

    @override
    def create(self, dsn: Dsn) -> ScriptedTransport:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "key", self._get_supported_schemes())
        _ = self._get_user(dsn)
        return ScriptedTransport(str(dsn.get_option("name", f"{dsn.scheme}://{dsn.host}")))

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("key", "smtp")


def _failures(cases: FactoryCases) -> list[str]:
    with pytest.raises(AssertionError) as caught:
        assert_factory_cases(cases)
    return str(caught.value).splitlines()


def test_it_passes_a_factory_that_does_what_its_cases_say() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_KeyFactory,
            supports=[
                (Dsn("key", "default"), True),
                (Dsn("smtp", "default"), True),
                (Dsn("other", "default"), False),
            ],
            create=[
                (Dsn("key", "default", USER, PASSWORD), ScriptedTransport("key://default")),
                (Dsn("smtp", "example.com", USER), ScriptedTransport("smtp://example.com")),
            ],
            unsupported_scheme=[
                (Dsn("other", "default", USER), None),
                (Dsn("other", "default", USER), 'The "other" scheme is not supported; '),
            ],
            incomplete_dsn=[Dsn("key", "default")],
        )
    )


def test_it_reports_every_case_a_factory_fails_at_once() -> None:
    cases = FactoryCases(
        create_factory=_KeyFactory,
        supports=[(Dsn("key", "default"), False), (Dsn("other", "default"), True)],
        create=[(Dsn("key", "default", USER), ScriptedTransport("key://other"))],
        unsupported_scheme=[(Dsn("key", "default", USER), None)],
        incomplete_dsn=[Dsn("key", "default", USER)],
    )

    assert _failures(cases) == [
        "The factory fails 5 case(s):",
        f"- it supports {_KEY}",
        f"- it does not support {_OTHER}",
        f"- {_KEY} creates 'key://default', not 'key://other'",
        f"- {_KEY} raised nothing, not UnsupportedSchemeError",
        f"- {_KEY} raised nothing, not IncompleteDsnError",
    ]


def test_a_transport_of_another_class_fails_its_create_case() -> None:
    cases = FactoryCases(
        create_factory=_KeyFactory, create=[(Dsn("key", "default", USER), NullTransport())]
    )

    assert _failures(cases)[1:] == [
        (
            f"- {_KEY} creates a tests.support.scripted_transport.ScriptedTransport, "
            "not a xtr_mailer.transport.NullTransport"
        ),
    ]


def test_a_create_case_compares_what_read_state_reads_instead_of_the_string() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_KeyFactory,
            create=[(Dsn("key", "default", USER), ScriptedTransport("another name"))],
            read_state=type,
        )
    )


def test_an_smtp_transport_must_read_as_its_scheme_then_its_host() -> None:
    dsn = Dsn("smtp", "example.com", USER, options={"name": "smtp://localhost"})
    cases = FactoryCases(
        create_factory=_KeyFactory, create=[(dsn, ScriptedTransport("smtp://localhost"))]
    )

    assert _failures(cases)[1:] == [
        f'- {dsn!r} creates "smtp://localhost", not "smtp://…example.com…"',
    ]


def test_a_create_case_raising_fails() -> None:
    cases = FactoryCases(
        create_factory=_KeyFactory,
        create=[(Dsn("key", "default"), ScriptedTransport("key://default"))],
    )

    assert _failures(cases)[1:] == [f"- {_KEY} raised IncompleteDsnError: User is not set."]


def test_a_refusal_with_another_error_or_text_fails_its_case() -> None:
    cases = FactoryCases(
        create_factory=_KeyFactory,
        unsupported_scheme=[
            (Dsn("other", "default", USER), "Missing token."),
            (Dsn("key", "default"), None),
        ],
        incomplete_dsn=[Dsn("other", "default")],
    )

    assert _failures(cases) == [
        "The factory fails 3 case(s):",
        f'- {_OTHER} raised UnsupportedSchemeError: {_UNSUPPORTED}, without "Missing token."',
        f"- {_KEY} raised IncompleteDsnError: User is not set., not UnsupportedSchemeError",
        f"- {_OTHER} raised UnsupportedSchemeError: {_UNSUPPORTED}, not IncompleteDsnError",
    ]
