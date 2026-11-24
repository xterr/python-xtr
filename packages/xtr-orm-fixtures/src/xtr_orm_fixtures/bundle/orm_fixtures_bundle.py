"""The xtr-orm-fixtures bundle: the application's fixtures, wherever they are, and their command."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from typing import Final, final, override

from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    named_factory,
    qualified_name,
    required_bundle,
)
from xtr_orm.bundle import OrmConfig

from xtr_orm_fixtures.fixture_interface import FixtureInterface
from xtr_orm_fixtures.purger import OrmPurgerFactory, PurgerFactoryInterface
from xtr_orm_fixtures.table_definitions import TableDefinitions

__all__ = ["DEFAULT_PURGER", "FIXTURE_TAG", "OrmFixturesBundle"]

FIXTURE_TAG: Final = "orm_fixtures.fixture"
"""The tag every fixture the application defines carries."""

DEFAULT_PURGER: Final = "default"
"""The name the purger factory built in is known by, and the one a run uses unless told."""


@final
@required_bundle("xtr_orm.bundle:OrmBundle")
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("orm_fixtures")
class OrmFixturesBundle(Bundle):
    """Registers every fixture class the application defines, and ``orm:fixtures:load``.

    Nothing is configured and nothing is scanned of the bundle's own: the
    application's scan finds the fixtures wherever the application keeps
    them, and each is built by the container, once per run, so it can take
    the services it needs in its constructor.

    A purger factory of the application's joins the built-in one under the
    name it is given: ``@as_alias(PurgerFactoryInterface, qualifier="mine")``.
    """

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register each fixture class the scan finds."""
        builder.register_attribute_for_autoconfiguration(_fixtures_in, _register_fixture)

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the connections' table definitions, the built-in purger, the command."""
        del config
        orm = builder.get_extension_config(OrmConfig)
        _ = services.set(named_factory(_table_definitions_factory(orm), "orm_fixtures_tables"))
        _ = services.set(OrmPurgerFactory)
        services.alias(PurgerFactoryInterface, OrmPurgerFactory, alias_qualifier=DEFAULT_PURGER)
        if bundle_active(builder, "console"):
            services.load("xtr_orm_fixtures.command")


def _fixtures_in(obj: object) -> Iterable[type]:
    """Yield ``obj`` when it is a fixture class that can be built.

    Read by inheritance, not by shape: a class is a fixture because it says
    so, never because it happens to have a ``load`` method. An abstract base,
    or an interface of the application's own, only lends to the fixtures
    built on it.
    """
    if not isinstance(obj, type) or FixtureInterface not in obj.__mro__:
        return ()
    if inspect.isabstract(obj) or vars(obj).get("_is_protocol", False):
        return ()
    return (obj,)


def _register_fixture(obj: object, fixture: type, services: ServiceConfigurator) -> None:
    """Register ``fixture``, built once per run, among the fixtures by its qualified name."""
    del obj
    _ = services.set(fixture, lifetime="scoped").add_tag(FIXTURE_TAG)
    services.alias(FixtureInterface, fixture, alias_qualifier=qualified_name(fixture))


def _table_definitions_factory(orm: OrmConfig) -> Callable[[], TableDefinitions]:
    """Build the factory of the table definitions of every connection ``orm`` configures.

    Each connection's are the ones its migrations compare the database with,
    so the run empties exactly the tables the application maps. They are read
    when the command first needs them, once every model is mapped.
    """

    def table_definitions() -> TableDefinitions:
        return TableDefinitions(
            {name: connection.table_definitions() for name, connection in orm.connections.items()}
        )

    return table_definitions
