# Persistence

`persistence` names exactly one store; the bundle registers its managers under the interfaces in
`xtr_security_oauth2_server.manager` (all methods async):

| Interface | Methods |
| --- | --- |
| `ClientManagerInterface` | `find(identifier)`, `save(client)`, `remove(client)`, `list(client_filter)` |
| `AccessTokenManagerInterface` | `find`, `save`, `clear_expired() -> int` |
| `RefreshTokenManagerInterface` | `find`, `save`, `revoke(identifier) -> bool` (true only for the call that revoked it), `clear_expired` |
| `AuthorizationCodeManagerInterface` | `find`, `save`, `clear_expired` |
| `DeviceCodeManagerInterface` | `find`, `find_by_user_code(code)`, `save`, `clear_expired` |
| `CredentialsRevokerInterface` (`xtr_security_oauth2_server.service`) | `revoke_credentials_for_user(user)`, `revoke_credentials_for_client(client)` |

`ClientFilter.create().add_grant_criteria(...).add_redirect_uri_criteria(...).add_scope_criteria(...)`
narrows `list`; a client must hold everything named.

## In memory

`InMemoryPersistenceConfig()`. Tests and demonstrations: everything is lost at exit, a command run
in another process sees an empty store, and a refresh token's single use holds within one process
only. No credentials revoker is registered.

## In a database

```python
# app/config/orm.py
from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, OrmConfig


@configure
def orm() -> OrmConfig:
    return OrmConfig(connections={"default": ConnectionConfig(url=env("DATABASE_URL"))})
```

```python
from xtr_security_oauth2_server.bundle import OrmPersistenceConfig

persistence = OrmPersistenceConfig()  # connection="default", table_prefix="oauth2_"
```

- Install xtr-orm beside this package and list `OrmBundle`; a database persistence without it
  fails the build naming it.
- The package ships the mapping, not revisions: its tables join the connection's definitions as
  the container compiles, and `orm:migrations:diff` then writes them into the application's
  revision. Apply it with the application's other migrations.
- Tables, under the prefix: `authorization_code` and `refresh_token` always; `access_token` while
  `persist_access_token`; `device_code` while the device flow is on; `client` only for the
  shipped `Client`. Credentials reference the client's `identifier` with `ON DELETE CASCADE`.
- Every write commits before the endpoint answers, refusals included (a device's last poll, a
  revoked code), so a token is never handed out that was not stored.
- SQLite enforces the cascade only with `PRAGMA foreign_keys=ON`.

## The application's own client class

Name it under `ClientConfig(classname=AppClient)`; the token tables then point at its table, and
no `oauth2_client` is created. `ClientMappingMixin` maps the registration columns onto it; the
class keeps its own base, table and columns:

```python
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.persistence.mapping import ClientMappingMixin


class Base(DeclarativeBase): ...


class AppClient(  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    ClientMappingMixin,
    AbstractClient,
    Base,
):
    __tablename__ = "app_client"

    _identifier: Mapped[str] = mapped_column(  # pyright: ignore[reportIncompatibleVariableOverride]
        "identifier", String(32), primary_key=True
    )
    tenant: Mapped[str | None] = mapped_column("tenant", String(32), nullable=True)
```

- The two suppressions are needed: the declarative base brings a constructor `AbstractClient`'s
  replaces (`reportUnsafeMultipleInheritance`), and the mixin and `_identifier` map columns onto
  attributes `AbstractClient` declares (`reportIncompatibleVariableOverride`).
- `AbstractClient(name, identifier, secret)` stays the constructor; a load does not run it.
- On a base with a primary key of its own (`UUIDAuditBase`), declare `_identifier` with
  `unique=True, nullable=False` instead of `primary_key=True`.
- The token tables are built into the metadata the connection reads, which must hold the
  class's table: `ConnectionConfig(metadata=Base.metadata)` for a plain declarative base; an
  advanced-alchemy base registers in the metadata a connection reads when it names none.
- One client class per process.

## Stores of the application's own

```python
from xtr_security_oauth2_server.bundle import CustomPersistenceConfig

persistence = CustomPersistenceConfig(
    access_token_manager=AccessTokenStore,
    authorization_code_manager=AuthorizationCodeStore,
    client_manager=ClientStore,
    refresh_token_manager=RefreshTokenStore,
    device_code_manager=DeviceCodeStore,
    credentials_revoker=CredentialsRevoker,
)
```

Each named class implements its interface and is a registered service (`@as_service`, or the
application's own bundle); the bundle aliases the interface to it, and refuses the build naming
every one that is not registered. All six are required. A client manager announces
`OAuth2Events.PRE_SAVE_CLIENT` before each save; `RefreshTokenManagerInterface.revoke` must be
atomic (a conditional update), which is what keeps two concurrent refreshes from both succeeding.
An application keeping no access token (`persist_access_token=False`) still names one: the
`AccessTokenManager` of `xtr_security_oauth2_server.manager.null`, registered as a service, stores
nothing.

## Sweeping

`oauth2-server:clear-expired-tokens` (or `-a`, `-r`, `-c`, `-dc` for one store each) deletes what
expired; an expired credential is refused anyway, so this is housekeeping to schedule.
