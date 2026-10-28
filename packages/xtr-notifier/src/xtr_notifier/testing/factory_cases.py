"""What a provider's transport factory must do, as data a test hands to the checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import final

from xtr_notifier.transport import TransportFactoryInterface

__all__ = ["FactoryCases"]


@final
@dataclass(frozen=True, slots=True)
class FactoryCases:
    """The cases :func:`~xtr_notifier.testing.assert_factory_cases` drives a factory over.

    Each refusal pairs a DSN with the text its error must contain, or ``None``
    to check the error's type alone. The sequences are copied into tuples, so
    the cases cannot change half way through a run.

    Attributes:
        create_factory: Builds the factory under test.
        supports: Pairs of whether the factory must serve a DSN, and that DSN.
        create: Pairs of the string the transport built from a DSN must read
            as, and that DSN.
        unsupported_scheme: DSNs ``create`` must refuse with
            :class:`~xtr_notifier.exception.UnsupportedSchemeError`.
        incomplete_dsn: DSNs ``create`` must refuse with
            :class:`~xtr_notifier.exception.IncompleteDsnError` — a missing token,
            a malformed one.
        missing_required_option: DSNs ``create`` must refuse with
            :class:`~xtr_notifier.exception.MissingRequiredOptionError`.
    """

    create_factory: Callable[[], TransportFactoryInterface]
    supports: Sequence[tuple[bool, str]] = field(default_factory=tuple[tuple[bool, str], ...])
    create: Sequence[tuple[str, str]] = field(default_factory=tuple[tuple[str, str], ...])
    unsupported_scheme: Sequence[tuple[str, str | None]] = field(
        default_factory=tuple[tuple[str, str | None], ...]
    )
    incomplete_dsn: Sequence[tuple[str, str | None]] = field(
        default_factory=tuple[tuple[str, str | None], ...]
    )
    missing_required_option: Sequence[tuple[str, str | None]] = field(
        default_factory=tuple[tuple[str, str | None], ...]
    )

    def __post_init__(self) -> None:
        """Freeze the sequences, so the caller's lists cannot change the cases."""
        object.__setattr__(self, "supports", tuple(self.supports))
        object.__setattr__(self, "create", tuple(self.create))
        object.__setattr__(self, "unsupported_scheme", tuple(self.unsupported_scheme))
        object.__setattr__(self, "incomplete_dsn", tuple(self.incomplete_dsn))
        object.__setattr__(self, "missing_required_option", tuple(self.missing_required_option))
