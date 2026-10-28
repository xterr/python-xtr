"""Driving a provider's transport factory over its cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.exception import (
    IncompleteDsnError,
    MissingRequiredOptionError,
    UnsupportedSchemeError,
)
from xtr_notifier.transport import Dsn

from ._failures import raise_failures

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.transport import TransportFactoryInterface

    from .factory_cases import FactoryCases

__all__ = ["assert_factory_cases"]


def assert_factory_cases(cases: FactoryCases) -> None:
    """Check a factory against every one of ``cases``.

    For example::

        assert_factory_cases(
            FactoryCases(
                create_factory=lambda: AcmeTransportFactory(MockHttpClient()),
                supports=[(True, "acme://TOKEN@default"), (False, "other://TOKEN@default")],
                create=[("acme://api.acme.test", "acme://TOKEN@default")],
                unsupported_scheme=[("other://TOKEN@default", None)],
                incomplete_dsn=[("acme://default", "Missing token.")],
            )
        )

    Raises:
        AssertionError: Listing every case the factory fails. Raised rather
            than asserted, so the check holds however the suite is run.
    """
    factory = cases.create_factory()
    failures = [
        f'it {"does not support" if expected else "supports"} "{dsn}"'
        for expected, dsn in cases.supports
        if factory.supports(Dsn(dsn)) is not expected
    ]
    for expected, dsn in cases.create:
        failures.extend(_creation_failures(factory, dsn, expected))
    refusals: Sequence[tuple[type[Exception], Sequence[tuple[str, str | None]]]] = (
        (UnsupportedSchemeError, cases.unsupported_scheme),
        (IncompleteDsnError, cases.incomplete_dsn),
        (MissingRequiredOptionError, cases.missing_required_option),
    )
    for error_type, refused in refusals:
        for dsn, text in refused:
            failures.extend(_refusal_failures(factory, dsn, (error_type, text)))
    raise_failures("factory", failures)


def _creation_failures(factory: TransportFactoryInterface, dsn: str, expected: str) -> list[str]:
    """Return how the transport ``factory`` builds from ``dsn`` fails to read as ``expected``."""
    try:
        created = str(factory.create(Dsn(dsn)))
    except Exception as error:  # noqa: BLE001 -- any error is the failure being reported
        return [f'"{dsn}" raised {type(error).__name__}: {error}']
    return [] if created == expected else [f'"{dsn}" creates "{created}", not "{expected}"']


def _refusal_failures(
    factory: TransportFactoryInterface, dsn: str, refusal: tuple[type[Exception], str | None]
) -> list[str]:
    """Return how ``factory`` fails to refuse ``dsn`` with the error and text of ``refusal``."""
    error_type, text = refusal
    try:
        _ = factory.create(Dsn(dsn))
    except error_type as error:
        if text is None or text in str(error):
            return []
        return [f'"{dsn}" raised {type(error).__name__}: {error}, without "{text}"']
    except Exception as error:  # noqa: BLE001 -- any other error is the failure being reported
        return [f'"{dsn}" raised {type(error).__name__}: {error}, not {error_type.__name__}']
    return [f'"{dsn}" raised nothing, not {error_type.__name__}']
