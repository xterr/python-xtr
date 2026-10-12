"""Serving the stored deployment: its kernel, its tables, and the reset after it.

A stored deployment maps its models when the container is built and keeps them
mapped for the life of the process, which is right for a deployment and wrong
for a test run: the next test builds definitions of its own, and a model mapped
onto somebody else's table is refused. So the mapping is taken back on the way
out, the way the driver's own tests take theirs back.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

from advanced_alchemy.base import metadata_registry
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from xtr_dependency_injection import Kernel
from xtr_orm.bundle import OrmBundle

from tests.fixtures.oauth2_orm_app.config import BIND_KEY, URL_VARIABLE
from tests.support.orm import enforce_foreign_keys
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.refresh_token import RefreshToken

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

__all__ = ["orm_kernel", "stored_tables", "stored_url", "unmapped"]

#: Every model a driver of this package maps.
_MODELS = (Client, AccessToken, AuthorizationCode, RefreshToken, DeviceCode)

_APP = "tests.fixtures.oauth2_orm_app"


def stored_url(tmp_path: Path) -> str:
    """Return the URL of the database the stored deployment reads and writes.

    A test that has to see a write the way another request would opens its own
    session on this, which is the only way to tell a commit from a flush.
    """
    return f"sqlite+aiosqlite:///{tmp_path / 'oauth2.sqlite'}"


def orm_kernel(tmp_path: Path) -> Kernel:
    """Return a kernel of the stored deployment, on a SQLite file under ``tmp_path``."""
    return Kernel(
        _APP,
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}, OrmBundle: {"all": True}},
        concurrent_scoped_access=True,
        environ={URL_VARIABLE: stored_url(tmp_path)},
    )


@contextmanager
def unmapped() -> Generator[None, None, None]:
    """Take back, on the way out, whatever mapping a built container installed.

    The mapping lives on the model classes, which the whole process shares.
    Each model's registry is the driver's own, so disposing it takes back
    exactly what that driver installed — and whatever the mapping stood in
    for, which unmapping deletes, is put back as it was found. That is the
    driver's own reset, done from outside: a deployment maps once and keeps
    it, so nothing in the container hands a test the way back.
    """
    declared: dict[type[object], dict[str, object]] = {
        model: dict(vars(model)) for model in _MODELS
    }
    try:
        yield
    finally:
        _dispose_registries()
        for model in _MODELS:
            held = vars(model)
            for name, value in declared[model].items():
                # Unmapping deletes every attribute the mapping installed, and
                # one of those stood in for something the model declares
                # itself — the access token a refresh token names when none
                # was stored.
                if name not in held:
                    setattr(model, name, value)


def _dispose_registries() -> None:
    """Let go of every registry a driver mapped these models in.

    One registry holds them all, so the first one found unmaps the rest; the
    others are looked for all the same, in case a deployment mapped only some.
    """
    for model in _MODELS:
        try:
            mapper = class_mapper(model)
        except UnmappedClassError:
            continue
        mapper.registry.dispose()


@asynccontextmanager
async def stored_tables(tmp_path: Path) -> AsyncGenerator[None, None]:
    """Create the tables the bundle's driver mapped, and unmap them afterwards.

    The definitions are the ones the mappings pass loaded into this
    application's bind key — the very tables a revision would create — so what
    the flows run against is what a deployment would have migrated.
    """
    with unmapped():
        async with await orm_kernel(tmp_path).boot() as booted:
            engine = await booted.container.get(AsyncEngine)
            enforce_foreign_keys(engine)
            definitions = metadata_registry.get(BIND_KEY)
            async with engine.begin() as connection:
                await connection.run_sync(definitions.create_all)
        yield
