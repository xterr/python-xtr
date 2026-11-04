"""What a transport factory must do, as data a test hands to the checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, final

from xtr_mailer.transport import Dsn, TransportFactoryInterface, TransportInterface

__all__ = ["PASSWORD", "USER", "FactoryCases"]

#: A user for the cases' DSNs; the ``$`` must come through the DSN as it was written.
USER: Final = "u$er"
#: A password for the cases' DSNs; the ``$`` must come through the DSN as it was written.
PASSWORD: Final = "pa$s"  # noqa: S105 -- a stand-in the cases' DSNs carry, guarding nothing


@final
@dataclass(frozen=True, slots=True)
class FactoryCases:
    """The cases :func:`~xtr_mailer.testing.assert_factory_cases` drives a factory over.

    Every transport factory owes the same things — to serve its schemes and no other, to build
    the transport a DSN describes, to refuse a scheme it does not serve and a DSN missing what
    its transport needs — so a factory's test states its cases here and the checks are written
    once. The sequences are copied into tuples, so the cases cannot change half way through a
    run.

    Attributes:
        create_factory: Builds the factory under test.
        supports: Pairs of a DSN and whether the factory must serve it.
        create: Pairs of a DSN and the transport the factory must build from it: one of the
            same class, which ``read_state`` reads the same as.
        unsupported_scheme: Pairs of a DSN ``create`` must refuse with
            :class:`~xtr_mailer.exception.UnsupportedSchemeError` and the text its error must
            contain, or ``None`` to check the error's type alone.
        incomplete_dsn: DSNs ``create`` must refuse with
            :class:`~xtr_mailer.exception.IncompleteDsnError` — a user or a password missing.
        read_state: Reads what two transports built alike agree on: their string form, unless
            given. A transport's string never shows its credentials, nor every setting a DSN
            option makes, so a factory whose transports carry those reads them here.
    """

    create_factory: Callable[[], TransportFactoryInterface]
    supports: Sequence[tuple[Dsn, bool]] = field(default_factory=tuple[tuple[Dsn, bool], ...])
    create: Sequence[tuple[Dsn, TransportInterface]] = field(
        default_factory=tuple[tuple[Dsn, TransportInterface], ...]
    )
    unsupported_scheme: Sequence[tuple[Dsn, str | None]] = field(
        default_factory=tuple[tuple[Dsn, str | None], ...]
    )
    incomplete_dsn: Sequence[Dsn] = field(default_factory=tuple[Dsn, ...])
    read_state: Callable[[TransportInterface], object] = str

    def __post_init__(self) -> None:
        """Freeze the sequences, so the caller's lists cannot change the cases."""
        object.__setattr__(self, "supports", tuple(self.supports))
        object.__setattr__(self, "create", tuple(self.create))
        object.__setattr__(self, "unsupported_scheme", tuple(self.unsupported_scheme))
        object.__setattr__(self, "incomplete_dsn", tuple(self.incomplete_dsn))
