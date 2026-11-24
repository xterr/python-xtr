"""An application's fixtures, found, built and loaded by its kernel, and left out where they must.

The application, ``shop_app``, keeps fixtures in two folders: one injecting
services, one importing ``fakerish``, a stand-in for a fake-data library a
project installs for development only. A helper imports ``fakerish`` alone. Each
test writes the application and decides what is installed: ``fakerish`` or not,
this package or not.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import text
from xtr_console import Application, ApplicationTester, ExitCode
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import SetAsideModuleUsedError
from xtr_orm import ConnectionRegistry

from tests.support.scratch import ScratchSite, hide_package

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import MetaData
    from xtr_dependency_injection.diagnostics import KernelReport

pytestmark = pytest.mark.anyio

APP = "shop_app"

MODELS = """
from sqlalchemy import ForeignKey, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData()


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
"""

CONFIG = """
from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, OrmConfig

from shop_app.models import Base


@configure
def orm() -> OrmConfig:
    return OrmConfig(
        connections={"default": ConnectionConfig(url=env("SHOP_URL"), metadata=Base.metadata)}
    )
"""

NAMING = """
from xtr_dependency_injection import as_service


@as_service
class Naming:
    def group(self) -> str:
        return "staff"
"""

FIXTURE_BASE = """
from abc import ABC, abstractmethod

from xtr_orm_fixtures import Fixture


class NamedFixture(Fixture, ABC):
    @abstractmethod
    def label(self) -> str: ...
"""

GROUP_FIXTURES = """
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_orm import ConnectionRegistry

from shop_app.catalog.base import NamedFixture
from shop_app.models import Group
from shop_app.naming import Naming

SESSIONS = []


class GroupFixtures(NamedFixture):
    def __init__(
        self, naming: Naming, session: AsyncSession, connections: ConnectionRegistry
    ) -> None:
        self._naming = naming
        self._session = session
        self._connections = connections

    def label(self) -> str:
        return "groups"

    async def load(self, session: AsyncSession) -> None:
        SESSIONS.append(session is self._session and session is await self._connections.session())
        group = Group(name=self._naming.group())
        session.add(group)
        self.add_reference("staff", group)
"""

USER_FIXTURES = """
import fakerish
from xtr_orm_fixtures import DependentFixtureInterface, Fixture

from shop_app.catalog.groups import GroupFixtures
from shop_app.models import Group, User


class UserFixtures(Fixture, DependentFixtureInterface):
    def get_dependencies(self):
        return (GroupFixtures,)

    async def load(self, session) -> None:
        group = self.get_reference("staff", Group)
        session.add(User(name=fakerish.name(), group_id=group.id))
"""

HELPERS = """
import fakerish


def fake_email() -> str:
    return fakerish.email()
"""

PURGING = """
from xtr_dependency_injection import as_alias, when
from xtr_orm_fixtures.purger import OrmPurger, PurgerFactoryInterface

PICKED = []


@when("dev", "test")
@as_alias(PurgerFactoryInterface, qualifier="keep_groups")
class KeepGroupsPurgerFactory(PurgerFactoryInterface):
    def create_for_connection(
        self, connection, metadata, *, excluded=(), purge_with_truncate=False
    ):
        PICKED.append(connection)
        return OrmPurger(metadata, (*excluded, "groups"))
"""

FAKERISH = """
def name() -> str:
    return "ada"


def email() -> str:
    return "ada@example.com"
"""

DEV_TOOLS = """
from xtr_dependency_injection import Bundle, as_bundle


@as_bundle("dev_tools")
class DevToolsBundle(Bundle):
    pass
"""


def _bundles(fixtures: str, *, console: bool = True, dev_tools: bool = False) -> str:
    imports = ["from xtr_orm.bundle import OrmBundle"]
    listed = ['OrmBundle: {"all": True}']
    if console:
        imports.append("from xtr_console.bundle import ConsoleBundle")
        listed.append('ConsoleBundle: {"all": True}')
    imports.append("from xtr_orm_fixtures.bundle import OrmFixturesBundle")
    listed.append(f"OrmFixturesBundle: {fixtures}")
    if dev_tools:
        imports.append("from dev_tools import DevToolsBundle")
        listed.append('DevToolsBundle: {"dev": True}')
    return "\n".join(imports) + "\n\nBUNDLES = {" + ", ".join(listed) + "}\n"


DEV_TEST = '{"dev": True, "test": True}'
EVERYWHERE = '{"all": True}'


@pytest.fixture
def site(tmp_path: Path) -> Iterator[ScratchSite]:
    built = ScratchSite(tmp_path / "app")
    yield built
    built.unload()


@pytest.fixture
def libraries(tmp_path: Path) -> Iterator[ScratchSite]:
    built = ScratchSite(tmp_path / "libraries")
    built.write({"fakerish.__init__": FAKERISH})
    yield built
    built.unload()


def _write(site: ScratchSite, monkeypatch: pytest.MonkeyPatch, bundles: str) -> None:
    site.write(
        {
            f"{APP}.__init__": "",
            f"{APP}.bundles": bundles,
            f"{APP}.config": CONFIG,
            f"{APP}.models": MODELS,
            f"{APP}.naming": NAMING,
            f"{APP}.catalog.base": FIXTURE_BASE,
            f"{APP}.catalog.groups": GROUP_FIXTURES,
            f"{APP}.people.users": USER_FIXTURES,
            f"{APP}.helpers": HELPERS,
            f"{APP}.purging": PURGING,
        }
    )
    site.install(monkeypatch)


def _kernel(env: str, database_url: str) -> Kernel:
    return Kernel(APP, env=env, environ={"SHOP_URL": database_url})


def _report(env: str, database_url: str) -> KernelReport:
    return _kernel(env, database_url).build().report


def _registered(report: KernelReport) -> set[str]:
    return {definition.provider_qualname for definition in report.definitions}


async def _run(
    env: str, database_url: str, argv: list[str]
) -> tuple[int, str, dict[str, list[str]]]:
    """Boot the application, create its tables holding the group ``old``, run ``argv``."""
    async with await _kernel(env, database_url).boot() as booted:
        engine = await (await booted.container.get(ConnectionRegistry)).engine()
        metadata = cast("MetaData", _module_value(f"{APP}.models", "Base").__dict__["metadata"])
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            _ = await connection.execute(text("insert into groups (id, name) values (1, 'old')"))
        tester = ApplicationTester(await booted.container.get(Application), width=200)
        code = await tester.execute(argv, interactive=False)
        async with engine.connect() as connection:
            rows = {
                table: cast(
                    "list[str]",
                    list(
                        (
                            await connection.execute(text(f"select name from {table} order by id"))
                        ).scalars()
                    ),
                )
                for table in ("groups", "users")
            }
    return code, " ".join((tester.display + tester.error_display).split()), rows


def _module_value(module: str, name: str) -> object:
    return cast("object", vars(importlib.import_module(module))[name])


async def test_command_loads_the_application_fixtures(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    code, shown, rows = await _run("test", database_url, ["orm:fixtures:load"])

    assert code == ExitCode.SUCCESS, shown
    assert "Loaded 2 fixtures." in shown
    assert rows == {"groups": ["staff"], "users": ["ada"]}


async def test_fixtures_are_found_in_any_folder(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    registered = _registered(_report("test", database_url))

    assert f"{APP}.catalog.groups:GroupFixtures" in registered
    assert f"{APP}.people.users:UserFixtures" in registered


async def test_abstract_fixture_bases_are_not_registered(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    registered = _registered(_report("test", database_url))

    assert f"{APP}.catalog.base:NamedFixture" not in registered


async def test_fixture_receives_injected_services(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    code, shown, rows = await _run("test", database_url, ["orm:fixtures:load"])

    assert code == ExitCode.SUCCESS, shown
    assert rows["groups"] == ["staff"]
    # The session a fixture injects is the one it is handed, the run's unit of work.
    assert _module_value(f"{APP}.catalog.groups", "SESSIONS") == [True]


async def test_custom_purger_is_selected_by_alias(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    argv = ["orm:fixtures:load", "--purger", "keep_groups"]
    code, shown, rows = await _run("test", database_url, argv)

    assert code == ExitCode.SUCCESS, shown
    assert _module_value(f"{APP}.purging", "PICKED") == ["default"]
    assert rows == {"groups": ["old", "staff"], "users": ["ada"]}


async def test_command_absent_without_console_bundle(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST, console=False))
    # The orm bundle runs the console wherever it is installed: absent, it is not installed.
    hide_package(monkeypatch, "xtr_console")

    registered = _registered(_report("test", database_url))

    assert f"{APP}.catalog.groups:GroupFixtures" in registered
    assert not any("LoadDataFixturesCommand" in name for name in registered)


async def test_dev_only_install_boots_in_prod_with_fixtures_set_aside(
    site: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    _write(site, monkeypatch, _bundles(DEV_TEST))
    hide_package(monkeypatch, "xtr_orm_fixtures")

    report = _report("prod", database_url)

    set_aside = {entry.module: entry.missing for entry in report.scan.set_aside}
    assert set_aside == {
        f"{APP}.catalog.base": ("xtr_orm_fixtures",),
        f"{APP}.catalog.groups": ("xtr_orm_fixtures",),
        f"{APP}.helpers": ("fakerish",),
        f"{APP}.people.users": ("fakerish", "xtr_orm_fixtures"),
        f"{APP}.purging": ("xtr_orm_fixtures",),
    }
    assert f"{APP}.naming:Naming" in _registered(report)
    async with await _kernel("prod", database_url).boot() as booted:
        tester = ApplicationTester(await booted.container.get(Application), width=200)
        assert await tester.execute(["debug:bundles"]) == ExitCode.SUCCESS

    listed = tester.display.split("Set aside", 1)[1]
    assert f"{APP}.people.users" in listed
    assert f"{APP}.catalog.groups" in listed


async def test_regular_install_with_bundle_everywhere_loads_in_prod(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(EVERYWHERE))

    code, shown, rows = await _run("prod", database_url, ["orm:fixtures:load"])

    assert code == ExitCode.SUCCESS, shown
    assert rows == {"groups": ["staff"], "users": ["ada"]}


async def test_regular_install_with_bundle_dev_test_registers_nothing_in_prod(
    site: ScratchSite, libraries: ScratchSite, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    libraries.install(monkeypatch)
    _write(site, monkeypatch, _bundles(DEV_TEST))

    report = _report("prod", database_url)

    registered = _registered(report)
    assert report.scan.set_aside == ()
    assert not any("Fixtures" in name for name in registered)
    assert f"{APP}.naming:Naming" in registered


async def test_bundle_active_with_a_set_aside_fixture_fails_the_build(
    site: ScratchSite, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    # A bundle listed for development does not run in prod: there, a missing library is
    # tolerated — but not under a fixture the fixtures bundle, running, would register.
    dev_tools = ScratchSite(tmp_path / "dev_tools")
    dev_tools.write({"dev_tools.__init__": DEV_TOOLS})
    dev_tools.install(monkeypatch)
    _write(site, monkeypatch, _bundles(EVERYWHERE, dev_tools=True))

    try:
        with pytest.raises(SetAsideModuleUsedError) as caught:
            _ = _report("prod", database_url)
    finally:
        dev_tools.unload()

    assert "UserFixtures" in str(caught.value)
    assert "fakerish" in str(caught.value)
