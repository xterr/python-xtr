"""AddOnCatalog: the add-ons a new project can start with, and how ``--with`` names them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .add_on import AddOn
from .add_on_choice import AddOnChoice
from .exception import UnknownAddOnError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["AddOnCatalog"]

_WEBAPP = ("webapp",)

_SHIPPED = (
    AddOn(
        "orm",
        "Database engines, sessions per unit of work and versioned migrations.",
        "xtr-orm",
        ("di", "console"),
        ("sqlite", "postgres", "mysql"),
        ("sqlite",),
        "database drivers",
    ),
    AddOn(
        "messenger",
        "A message bus: handlers, middleware, transports and consumers.",
        "xtr-messenger",
        ("di", "console"),
        ("amqp", "taskiq", "pydantic"),
        (),
        "transports and serializers",
    ),
    AddOn(
        "scheduler",
        "Recurring messages on the bus: cron and intervals.",
        "xtr-scheduler",
        ("di", "console", "cron"),
    ),
    AddOn(
        "event-dispatcher",
        "Events dispatched to listeners and subscribers by priority.",
        "xtr-event-dispatcher",
        ("di", "console"),
    ),
    AddOn(
        "cache",
        "Cache pools in memory, in files or in Redis.",
        "xtr-cache",
        ("di", "console"),
        ("redis",),
        (),
        "backends",
    ),
    AddOn("lock", "Locks around shared resources.", "xtr-lock", ("di",), ("redis",), (), "stores"),
    AddOn(
        "rate-limiter",
        "Limits on how often anything may happen.",
        "xtr-rate-limiter",
        ("di", "cache", "lock"),
        ("redis",),
        (),
        "stores",
    ),
    AddOn(
        "storage",
        "Files on local disk, in memory or in object stores.",
        "xtr-storage",
        ("di",),
        ("s3", "gcs"),
        (),
        "object stores",
    ),
    AddOn(
        "security",
        "Firewalls, authenticators, voters and password hashing.",
        "xtr-security",
        ("console",),
        templates=_WEBAPP,
    ),
    AddOn(
        "jwt",
        "Self-issued JSON Web Tokens: a token manager and a firewall authenticator.",
        "xtr-security-jwt",
        ("console",),
        templates=_WEBAPP,
    ),
)


@final
class AddOnCatalog:
    """The add-ons on offer, looked up and parsed by name.

    ``--with`` is a comma-separated list of names, each optionally followed by
    ``:`` and its variants joined with ``+`` — ``orm:sqlite+postgres,messenger``.
    A name given alone takes the add-on's default variants.
    """

    __slots__ = ("_add_ons",)

    def __init__(self, add_ons: Iterable[AddOn]) -> None:
        """Offer ``add_ons``, in the order given."""
        self._add_ons: dict[str, AddOn] = {add_on.name: add_on for add_on in add_ons}

    @classmethod
    def default(cls) -> AddOnCatalog:
        """Return the catalog of the add-ons this tool ships."""
        return cls(_SHIPPED)

    def available(self, template: str) -> tuple[AddOn, ...]:
        """Return the add-ons a project made from ``template`` can take, in catalog order."""
        return tuple(add_on for add_on in self._add_ons.values() if add_on.fits(template))

    def get(self, name: str, template: str) -> AddOn:
        """Return the add-on called ``name``, for a project made from ``template``.

        Raises:
            UnknownAddOnError: When no add-on has that name, or it does not fit
                the template.
        """
        add_on = self._add_ons.get(name)
        if add_on is None or not add_on.fits(template):
            names = ", ".join(each.name for each in self.available(template))
            raise UnknownAddOnError(name, f"a {template} project can take {names}")
        return add_on

    def choose(self, add_on: AddOn, variants: str | None) -> AddOnChoice:
        """Return ``add_on`` with the ``+``-separated ``variants`` picked.

        ``None`` takes the add-on's defaults; an empty string picks none.

        Raises:
            UnknownAddOnError: When a variant is not one the add-on offers.
        """
        if variants is None:
            return AddOnChoice(add_on, add_on.default_variants)
        picked = {variant.strip() for variant in variants.split("+") if variant.strip()}
        unknown = sorted(picked - set(add_on.variants))
        if unknown:
            offered = ", ".join(add_on.variants) or "none"
            raise UnknownAddOnError(
                f"{add_on.name}:{variants}",
                f"{', '.join(unknown)} is not one of its {add_on.variant_label} ({offered})",
            )
        return AddOnChoice(add_on, tuple(each for each in add_on.variants if each in picked))

    def parse(self, text: str, template: str) -> tuple[AddOnChoice, ...]:
        """Read a ``--with`` value into the add-ons it chooses, in the order written.

        Raises:
            UnknownAddOnError: When a name is unknown, does not fit the
                template, is given twice, or names a variant its add-on lacks.
        """
        chosen: dict[str, AddOnChoice] = {}
        for token in (each.strip() for each in text.split(",")):
            if not token:
                continue
            name, separator, variants = token.partition(":")
            add_on = self.get(name.strip(), template)
            if add_on.name in chosen:
                raise UnknownAddOnError(token, "it is chosen twice")
            chosen[add_on.name] = self.choose(add_on, variants if separator else None)
        return tuple(chosen.values())
