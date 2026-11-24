---
name: xtr-orm-fixtures
description: Seed development and test databases from fixture classes with xtr-orm-fixtures - a Fixture with async load(session), references shared by name, dependencies, numeric order and groups, an emptying in foreign-key order by DELETE or TRUNCATE, one transaction or a dry run, and the orm:fixtures:load command. Use when writing or ordering fixtures, sharing objects between them, loading JSON or CSV rows in a fixture, choosing what a run empties or keeps, writing a purger factory, loading fixtures without a container, reading MissingFixtureError, CircularReferenceError, ReferenceNotFoundError or SetAsideModuleUsedError, keeping a production install without development dependencies booting, or adding OrmFixturesBundle to an application on xtr-dependency-injection.
---

# xtr-orm-fixtures

A development-only package: fixture classes seed a database through xtr-orm's connections, in
one transaction after an emptying of the tables the application maps.

## Quick reference

| Need | Use |
| --- | --- |
| A fixture | `class X(Fixture)` with `async def load(self, session)` |
| Share an object | `self.add_reference("admin", user)`; later `self.get_reference("admin", User)` |
| Load after others | `DependentFixtureInterface.get_dependencies() -> (UserFixtures,)` |
| Load first, by number | `OrderedFixtureInterface.get_order() -> 1` (not with dependencies) |
| Load a subset | `FixtureGroupInterface.get_groups()` (classmethod); `--group demo` |
| Run them | `uv run app orm:fixtures:load` (`-n`, `--append`, `--dry-run`, `--group`, `--connection`, `--purger`, `--purge-exclusions`, `--purge-with-truncate`) |
| Without a container | `Loader().load_from_package("app.fixtures")`, then `OrmExecutor(session, OrmPurger(metadata)).execute(loader.get_fixtures())` |

- Imports: `Fixture`, the interfaces, `Loader`, `ReferenceRepository`, `TableDefinitions` from
  `xtr_orm_fixtures`; `OrmExecutor`, `DryRunOrmExecutor` from `xtr_orm_fixtures.executor`;
  `OrmPurger`, `OrmPurgerFactory`, `PurgeMode`, `PurgerFactoryInterface` from
  `xtr_orm_fixtures.purger`; `OrmFixturesBundle` from `xtr_orm_fixtures.bundle`.
- Fixtures live anywhere in the application; the bundle finds every concrete class with
  `FixtureInterface` among its bases. An abstract base is not registered.

## A fixture with references

```python
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from xtr_orm_fixtures import DependentFixtureInterface, Fixture, FixtureInterface

from app.models import Order, User


class UserFixtures(Fixture):
    async def load(self, session: AsyncSession) -> None:
        admin = User(email="admin@example.com")
        session.add(admin)
        self.add_reference("admin", admin)


class OrderFixtures(Fixture, DependentFixtureInterface):
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (UserFixtures,)

    async def load(self, session: AsyncSession) -> None:
        session.add(Order(customer=self.get_reference("admin", User)))
```

The executor flushes after each fixture and commits once at the end: never commit in `load`.
Names are kept per class (a mapped object under its mapped class). `add_reference` refuses a
taken name; `set_reference` replaces it.

## A fixture with services

With the bundle, the container builds each fixture once per run, so its constructor takes
services — `AsyncSession` included, the same session `load` is handed:

```python
class CatalogFixtures(Fixture):
    def __init__(self, pricing: PricingService) -> None:
        self._pricing = pricing

    async def load(self, session: AsyncSession) -> None:
        session.add(Book(title="Dune", price=self._pricing.list_price("dune")))
```

## Rows from a file

```python
from pathlib import Path

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.utils.fixtures import open_fixture_async


class CountryRepository(SQLAlchemyAsyncRepository[Country]):
    model_type = Country


class CountryFixtures(Fixture):
    async def load(self, session: AsyncSession) -> None:
        rows = await open_fixture_async(Path(__file__).parent / "data", "countries")
        await CountryRepository(session=session).add_many([Country(**row) for row in rows])
```

## What a run empties

- Each connection's table definitions — `ConnectionConfig.table_definitions()`, what its
  migrations compare with — children before parents. Nothing else in the database.
- `--purge-exclusions countries` keeps a table; `--purge-with-truncate` uses `TRUNCATE`
  (PostgreSQL: one statement, no `CASCADE`; MySQL: checks off, each table, commits; SQLite:
  `DELETE`).
- A purger of your own, picked with `--purger keep_countries`:

  ```python
  from xtr_dependency_injection import as_alias, when
  from xtr_orm_fixtures.purger import OrmPurger, PurgerFactoryInterface


  @when("dev", "test")
  @as_alias(PurgerFactoryInterface, qualifier="keep_countries")
  class KeepCountriesPurgerFactory(PurgerFactoryInterface):
      def create_for_connection(
          self, connection, metadata, *, excluded=(), purge_with_truncate=False
      ):
          return OrmPurger(metadata, (*excluded, "countries"))
  ```

## Testing

- Load fixtures into a test database with the executor directly: `Loader`,
  `OrmExecutor(session, OrmPurger(Base.metadata))`, `execute(loader.get_fixtures())`.
- `DryRunOrmExecutor` runs everything and rolls it back: a constraint a fixture breaks still
  fails it.
- Inside a transaction a test opened, the executor takes a savepoint and leaves the
  transaction to the test.
- A fixture is a plain class: build it, hand it a `ReferenceRepository` with
  `set_reference_repository`, and `await fixture.load(session)`.

## Use in an application

1. **Install** — `uv run xtr-recipes recipes:add --dev xtr-orm-fixtures` (or
   `uv add --dev xtr-orm-fixtures`, then `uv run xtr-recipes recipes:sync`). The database driver
   is xtr-orm's extra.
2. **Recipe** — lists the bundle for `dev` and `test`, and nothing else.
3. **Activate** — `from xtr_orm_fixtures.bundle import OrmFixturesBundle` in
   `<app>/config/bundles.py`, and `OrmFixturesBundle: {"dev": True, "test": True}` in `BUNDLES`.
   To seed production too, install it as a runtime dependency and list it `{"all": True}`.
4. **Brings along** — the orm bundle; `orm:fixtures:load` when the console bundle is active.
5. **Configure** — nothing.
6. **Environment** — nothing.
7. **Ignore** — nothing: fixtures are code to commit.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-orm-fixtures`, then delete the fixtures.
9. **Check** — `debug:bundles` lists `orm_fixtures` active in `dev`; in production without the
   dev dependencies, it is not active and the fixture modules are listed under **Set aside**.

## Errors

Every one derives from `OrmFixturesError`, in `xtr_orm_fixtures.exception`:

| Error | Raised when |
| --- | --- |
| `InvalidArgumentError` | A fixture is numbered and dependent, depends on nothing or itself; a reference is asked for before a run; an unknown connection |
| `MissingFixtureError` | A dependency was not added (`fixture`, `required_by`) |
| `CircularReferenceError` | Fixtures depend on one another in a circle (`fixtures`) |
| `ReferenceNotFoundError` | `get_reference` of a name not kept for that class |
| `ReferenceExistsError` | `add_reference` of a taken name; use `set_reference` |

In production, a fixture module set aside while the fixtures bundle runs fails the build with
the container's `SetAsideModuleUsedError`, naming the fixture and the missing package.

## Do not

- Do not import a fixture, or anything only fixtures use, from production code: that module is
  set aside where the package is not installed.
- Do not make it a runtime dependency without listing the bundle where it is needed, and the
  libraries the fixtures import as runtime dependencies too.
- Do not declare a service (`@as_alias`, `@as_service`) in a fixture module without
  `@when("dev", "test")`: a production build without the package refuses it.
- Do not commit or roll back inside `load`; the run does it once.
- Do not depend on `--purge-with-truncate` rolling back on MySQL: `TRUNCATE` commits there.
