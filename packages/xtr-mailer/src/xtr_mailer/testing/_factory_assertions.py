"""Driving a transport factory over its cases."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from xtr_mailer._error_text import type_name
from xtr_mailer.exception import IncompleteDsnError, UnsupportedSchemeError

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mailer.transport import Dsn, TransportFactoryInterface, TransportInterface

    from .factory_cases import FactoryCases

__all__ = ["assert_factory_cases"]

#: The schemes whose transport must read as the scheme, then somewhere the DSN's host.
_SMTP_SCHEMES: Final = ("smtp", "smtps")


def assert_factory_cases(cases: FactoryCases) -> None:
    """Check a transport factory against every one of ``cases``.

    For example::

        assert_factory_cases(
            FactoryCases(
                create_factory=lambda: AcmeTransportFactory(http_client=MockHttpClient()),
                supports=[(Dsn("acme", "default"), True), (Dsn("other", "default"), False)],
                create=[(Dsn("acme", "default", USER), AcmeTransport(USER, MockHttpClient()))],
                unsupported_scheme=[(Dsn("other", "default", USER), None)],
                incomplete_dsn=[Dsn("acme", "default")],
            )
        )

    A transport built for ``smtp`` or ``smtps`` must also read as ``smtp://…host…``, the
    scheme first and the DSN's host somewhere after it, whatever ``read_state`` reads.

    Raises:
        AssertionError: Listing every case the factory fails. Raised rather than asserted, so
            the check holds however the suite is run.
    """
    factory = cases.create_factory()
    failures = [
        f"it {'does not support' if expected else 'supports'} {dsn!r}"
        for dsn, expected in cases.supports
        if factory.supports(dsn) is not expected
    ]
    for case in cases.create:
        failures.extend(_creation_failures(factory, case, cases.read_state))
    for dsn, text in cases.unsupported_scheme:
        failures.extend(_refusal_failures(factory, dsn, (UnsupportedSchemeError, text)))
    for dsn in cases.incomplete_dsn:
        failures.extend(_refusal_failures(factory, dsn, (IncompleteDsnError, None)))
    if failures:
        listed = "\n".join(f"- {failure}" for failure in failures)
        raise AssertionError(f"The factory fails {len(failures)} case(s):\n{listed}")


def _creation_failures(
    factory: TransportFactoryInterface,
    case: tuple[Dsn, TransportInterface],
    read_state: Callable[[TransportInterface], object],
) -> list[str]:
    """Return how the transport ``factory`` builds from ``case``'s DSN is not the one expected."""
    dsn, expected = case
    try:
        created = factory.create(dsn)
    except Exception as error:  # noqa: BLE001 -- any error is the failure being reported
        return [f"{dsn!r} raised {type(error).__name__}: {error}"]
    if type(created) is not type(expected):
        return [f"{dsn!r} creates a {type_name(type(created))}, not a {type_name(type(expected))}"]
    failures: list[str] = []
    if (state := read_state(created)) != (expected_state := read_state(expected)):
        failures.append(f"{dsn!r} creates {state!r}, not {expected_state!r}")
    pattern = f"{re.escape(dsn.scheme)}://.*{re.escape(dsn.host)}.*"
    if dsn.scheme in _SMTP_SCHEMES and re.fullmatch(pattern, str(created)) is None:
        failures.append(f'{dsn!r} creates "{created}", not "{dsn.scheme}://…{dsn.host}…"')
    return failures


def _refusal_failures(
    factory: TransportFactoryInterface, dsn: Dsn, refusal: tuple[type[Exception], str | None]
) -> list[str]:
    """Return how ``factory`` fails to refuse ``dsn`` with the error and text of ``refusal``."""
    error_type, text = refusal
    try:
        _ = factory.create(dsn)
    except error_type as error:
        if text is None or text in str(error):
            return []
        return [f'{dsn!r} raised {type(error).__name__}: {error}, without "{text}"']
    except Exception as error:  # noqa: BLE001 -- any other error is the failure being reported
        return [f"{dsn!r} raised {type(error).__name__}: {error}, not {error_type.__name__}"]
    return [f"{dsn!r} raised nothing, not {error_type.__name__}"]
