<div align="center">

# xtr-orm-fixtures

**Seed a database from fixture classes: ordered, grouped and sharing references, loaded in one
transaction after an emptying in foreign-key order.**

</div>

---

## Why?

A development database is only useful with data in it: the users you log in as, the catalogue
the pages list, the orders a report counts. Writing that data by hand after every reset is slow,
and a SQL dump drifts from the models the day a column is added.

Fixtures are that data as code — classes written against the application's own models, loaded
in one command:

- 🧩 **A fixture is a class** with `async def load(self, session)`. It adds objects to the
  session it is handed, and with a container its constructor takes any service it needs.
- 🔗 **References** hand objects from one fixture to the next by name: the users fixture adds
  `"admin"`, the orders fixture places an order for it.
- 🧭 **Order without bookkeeping**: a fixture names the fixtures it depends on, or a number;
  groups load a subset — `--group demo` — with everything it depends on.
- 🧹 **An emptying in foreign-key order** first — `DELETE`, or `TRUNCATE` where the database has
  it — of exactly the tables the application maps, nothing else in the database.
- 🔒 **One transaction**: the emptying and every fixture commit together, or not at all. A dry run
  does all of it and rolls it back.
- 🌱 **Development-only**: listed for `dev` and `test`, absent from a production install — whose
  application modules may still import it.

## Install

```sh
uv add --dev xtr-orm-fixtures
```

It is a development dependency: production does not install it. It works on
[xtr-orm](../xtr-orm)'s connections; the database driver is xtr-orm's to bring, through its
`postgres`, `sqlite` or `mysql` extra. With [xtr-console](../xtr-console) installed beside it, the
bundle registers `orm:fixtures:load`.

## Quick start

A fixture, without a container:

```python
# app/fixtures/users.py
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_orm_fixtures import Fixture

from app.models import User


class UserFixtures(Fixture):
    async def load(self, session: AsyncSession) -> None:
        admin = User(email="admin@example.com")
        session.add(admin)
        self.add_reference("admin", admin)
```

Loaded by hand — the loader finds every fixture class the package's modules define, builds each
with no arguments and orders them; the executor empties the tables and loads them in one
transaction:

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from xtr_orm_fixtures import Loader
from xtr_orm_fixtures.executor import OrmExecutor
from xtr_orm_fixtures.purger import OrmPurger

from app.models import Base

engine = create_async_engine("sqlite+aiosqlite:///app.db")
loader = Loader()
loader.load_from_package("app.fixtures")
async with AsyncSession(engine) as session:
    await OrmExecutor(session, OrmPurger(Base.metadata)).execute(loader.get_fixtures())
```

In an application, the bundle does all of that: `uv run app orm:fixtures:load`.

## Writing fixtures

Subclass `Fixture` and write `load`. Add objects to the session; the executor flushes after each
fixture, so the next one sees their keys, and commits once every fixture has loaded. Never commit
or roll back inside `load`.

**References.** `add_reference(name, obj)` keeps an object for the fixtures after it, refusing a
name taken (`ReferenceExistsError`); `set_reference` replaces it. `get_reference(name, User)`
returns it typed, or raises `ReferenceNotFoundError`; `has_reference(name, User)` asks. Names
are kept per class — a mapped object under its mapped class — so `"admin"` may name a `User`
and a `Group` both. The session is never cleared, so a reference is the live object it tracks.

**Dependencies.** A fixture that needs another's references says so:

```python
from collections.abc import Sequence

from xtr_orm_fixtures import DependentFixtureInterface, Fixture, FixtureInterface


class OrderFixtures(Fixture, DependentFixtureInterface):
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (UserFixtures,)

    async def load(self, session: AsyncSession) -> None:
        session.add(Order(customer=self.get_reference("admin", User)))
```

**Order by number.** `OrderedFixtureInterface.get_order()` returns a number; numbered fixtures
load first, lowest first. A fixture is ordered one way: numbered and dependent is refused, as are
empty dependencies and a fixture depending on itself (`InvalidArgumentError`). Fixtures nothing
orders load in the order they were found.

**Groups.** `FixtureGroupInterface.get_groups()` — a classmethod — names the groups a fixture is
in; every fixture is also in the group named after its class. `--group demo` loads the fixtures of
`demo` and every fixture they depend on, in the same order as a full run.

A dependency on a fixture that is not there raises `MissingFixtureError`; fixtures depending on
one another in a circle raise `CircularReferenceError`, naming them.

`FixtureInterface` alone — `async def load(self, session)` — is enough for a fixture that shares
no references; `Fixture` adds them.

## Data files

Rows kept in JSON or CSV are loaded inside `load` with what advanced-alchemy already has —
`open_fixture_async` reads `countries.json` (or `.csv`, gzipped or zipped), a repository adds them:

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

`upsert_many` keeps rows that are there. Leave `auto_commit` off: the run commits.

## Purging

Unless a run appends, it empties the database first. `OrmPurger(metadata, excluded=(), mode=...)`
empties every table of the table definitions it is given, a referencing table before the one it
references, and nothing else the database holds:

| `PurgeMode` | Empties with |
|---|---|
| `DELETE` (default) | `DELETE` on each table, inside the run's transaction |
| `TRUNCATE` | PostgreSQL: one `TRUNCATE` of every table, without `CASCADE`. MySQL and MariaDB: `TRUNCATE` per table with foreign key checks off, turned back on whatever happens. Anything else, SQLite included: `DELETE` |

`excluded` leaves tables as they are, by name or schema-qualified name — reference data a
migration wrote, say. A purger never commits.

A purger is built by a `PurgerFactoryInterface` — `create_for_connection(connection, metadata, *,
excluded=(), purge_with_truncate=False)` — so an application can empty its database its own way
and pick it by name with `--purger`. `OrmPurgerFactory` builds `OrmPurger`, and is the one named
`default`.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing
it undoes.

- **Install** — `uv run xtr-recipes recipes:add --dev xtr-orm-fixtures`, or
  `uv add --dev xtr-orm-fixtures` then `uv run xtr-recipes recipes:sync`: fixtures seed
  development and test databases, so the package is a development dependency. The database
  driver is [xtr-orm](../xtr-orm)'s to bring, through its `postgres`, `sqlite` or `mysql` extra.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below, and only that: it
  lists `OrmFixturesBundle` for `dev` and `test`, which is what this package's recipe declares.
  There is nothing for it to configure, no variable to write and nothing to ignore.
- **Activate** — import the bundle at the top of `<app>/config/bundles.py`, like every other one,
  and list it for `dev` and `test`:

  ```python
  # <app>/config/bundles.py
  from xtr_orm_fixtures.bundle import OrmFixturesBundle

  BUNDLES = {
      OrmFixturesBundle: {"dev": True, "test": True},
  }
  ```

  Production still starts without the development dependencies installed: there the kernel
  stands in for the bundle, which is not active, and sets aside every application module that
  needs this package or a library only development installs — see
  [Development-only packages](../xtr-dependency-injection/README.md#development-only-packages).
  To seed production as well — reference data, loaded with `--group` — install the package as a
  runtime dependency instead (`uv add xtr-orm-fixtures`) and list the bundle `{"all": True}`.
- **Brings along** — the orm bundle, which it requires. The console bundle is read, not required:
  `orm:fixtures:load` is registered when it is active.
- **Configure** — nothing: fixtures are found wherever the application keeps them, and what is
  emptied is each connection's table definitions, as its migrations see them. A purger factory of
  the application's joins under the name it gives, with
  `@as_alias(PurgerFactoryInterface, qualifier="mine")`; in a module production imports too, keep
  it to the environments the bundle runs in with `@when("dev", "test")`.
- **Environment** — nothing.
- **Ignore** — nothing: fixtures are code to commit.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-orm-fixtures`: it runs
  `uv remove --dev xtr-orm-fixtures`, and the sync after it drops the `BUNDLES` entry. Delete the
  fixture classes, which no longer import.
- **Check** — `debug:bundles` lists `orm_fixtures` as active in `dev`;
  `orm:fixtures:load --dry-run` loads every fixture and rolls it all back.

## Development-only installs

Fixtures, and the libraries only they use — a fake-data library, say — live anywhere in the
application, beside the code they seed for. A production install without development
dependencies (`uv sync --no-dev`) has neither this package nor those libraries, yet its kernel
imports every application module while it scans.

It still starts. The bundle list says the fixtures bundle does not run there, so the scan
[sets aside](../xtr-dependency-injection/README.md#development-only-packages) every module that
fails to import for a package that is not installed — the fixture modules, the helpers built on
the fake-data library — and registers nothing they define. `debug:bundles` lists them under
**Set aside**, with what each needs; one built only on a library no absent bundle accounts for is
*not expected*, and logged as a warning.

Two rules keep it so:

- **A production module never imports a fixture.** If it does, it is set aside too: nothing it
  defines is registered, and a service it declares fails the production build with
  `SetAsideModuleUsedError`. Keep fixtures, and what only they use, to themselves.
- **Nothing in a fixture module declares a service for production.** A purger factory under
  `@as_alias` in a module that imports this package fails a production build with
  `SetAsideModuleUsedError`, unless `@when("dev", "test")` keeps it to the environments the bundle
  runs in.

Two installs are strict instead:

- **Every listed bundle installed and active** — fixtures installed as a runtime dependency and
  the bundle listed `{"all": True}`, but the fake-data library only in the dev group. Nothing is
  set aside where every listed bundle runs: the build fails with `ResourceImportError: cannot
  import scanned module '<module>'`, caused by the `ModuleNotFoundError`. Install that library as
  a runtime dependency too, or this package as a development one.
- **The bundle active, some other listed bundle not** — the fixtures bundle would register a
  fixture whose module was set aside, so the build fails with `SetAsideModuleUsedError`:

  ```text
  app.fixtures.users:UserFixtures is used (bundle 'orm_fixtures' would register it), but its
  module 'app.fixtures.users' was set aside: it needs 'faker', not installed here. Install what
  provides 'faker', or stop importing it from 'app.fixtures.users'.
  ```

## Kernel / bundle

`OrmFixturesBundle` has no configuration and scans nothing of its own. It requires the orm bundle
and registers:

- **Every fixture class the application defines** — a concrete class with `FixtureInterface`
  among its bases, wherever the application's scan finds it. An abstract base is not one; a class
  that merely has a `load` method is not one either. Each is built by the container once per run,
  so its constructor takes services — the run's `AsyncSession` included, the same one `load` is
  handed. It is tagged `FIXTURE_TAG` (`"orm_fixtures.fixture"`) and collected as a
  `ServiceLocator[FixtureInterface]`, keyed by its qualified name.
- **`TableDefinitions`** — each connection's table definitions, read with xtr-orm's
  `ConnectionConfig.table_definitions()`: the tables its migrations compare the database with,
  so a run empties exactly those.
- **`OrmPurgerFactory`**, as the `PurgerFactoryInterface` named `DEFAULT_PURGER` (`"default"`).
  Another joins under its own name:

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

- **`orm:fixtures:load`**, when the console bundle is active.

## Console commands

`orm:fixtures:load` empties a connection's database, after asking, and loads every fixture:

| Option | Does |
|---|---|
| `--append` | Add to what the database holds; nothing is emptied or asked |
| `--dry-run` | Run everything, the emptying included, then roll it all back; nothing is asked |
| `--group NAME` | Only the fixtures of `NAME` and what they depend on; repeat for several |
| `--connection NAME` | The connection to load into; the default one when left out |
| `--purger NAME` | The purger factory to empty with; `default` when left out |
| `--purge-exclusions TABLE` | A table to leave as it is; repeat for several |
| `--purge-with-truncate` | Empty with `TRUNCATE` rather than `DELETE` |

It asks `Careful, database "<db>" will be purged. Do you want to continue?`; `-n` answers yes,
and a no exits successfully with nothing changed. Each step is written as it runs —
`  > purging database`, `  > loading app.fixtures.users.UserFixtures` — and the run ends with
`Loaded 2 fixtures.` (`... and rolled them back.` for a dry run).

| Exit code | When |
|---|---|
| `SUCCESS` | Loaded, or declined |
| `FAILURE` | An unknown connection; no fixture to load (in the groups named); a refused fixture, a missing dependency or a circle; a connection without a session |
| `INVALID` | An unknown `--purger`, naming the ones there are; a connection without table definitions, when emptying |

A fixture that fails takes everything back with it and its error is raised as it is.

## Errors

Every one derives from `OrmFixturesError`, in `xtr_orm_fixtures.exception`:

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | A fixture is numbered and dependent, depends on nothing or on itself; a fixture asks for a reference before a run gave it a repository; an executor without a purger is asked to empty; an unknown connection or one without definitions (also a `ValueError`) |
| `MissingFixtureError` | A fixture depends on one that was not added — `fixture`, `required_by` (also a `LookupError`) |
| `CircularReferenceError` | Fixtures depend on one another in a circle — `fixtures`, the circle's class names |
| `ReferenceNotFoundError` | `get_reference` of a name not kept for that class — `name`, `kind` (also a `LookupError`) |
| `ReferenceExistsError` | `add_reference` of a name taken for that class; use `set_reference` — `name`, `kind` |

## Known limitations

- **xtr-orm-messenger's messages tables cannot be told apart** in a connection's table
  definitions. xtr-orm adds them there only once that connection's migrator is built, so a run
  usually leaves them alone; where they are there — a migrator built earlier in the process, or
  mapped by the application — a run empties them. Keep them with
  `--purge-exclusions <messages table>`.
- **MySQL and MariaDB commit around every `TRUNCATE`**, so an emptying with
  `--purge-with-truncate` cannot be rolled back there, by a failing fixture or a dry run.
- **PostgreSQL's `TRUNCATE` refuses a table that a table left out references**, rather than
  emptying both: empty such a set with `DELETE`, or leave the referenced table out too.
- **The session is never cleared between fixtures**: a very large seed keeps every object it
  added in memory until the run ends.
- **`Loader.load_from_package` builds each fixture with no arguments**: a fixture whose
  constructor takes services is built by the container, through the bundle.
- **A set-aside module's top-level code runs once** while the scan learns what it defines, with
  stand-ins for what is missing — see the container's
  [Known limitations](../xtr-dependency-injection/README.md#known-limitations).

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-orm-fixtures`; run the commands below from there. The `python-xtr-orm-fixtures`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
