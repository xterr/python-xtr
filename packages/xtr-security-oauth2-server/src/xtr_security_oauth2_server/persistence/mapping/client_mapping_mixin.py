"""The registration columns an application's own client class inherits."""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 — read at runtime by the ORM

from sqlalchemy.orm import Mapped  # noqa: TC002 — read at runtime by the ORM

from xtr_security_oauth2_server.value_object.grant import (
    Grant as GrantValue,  # noqa: TC001 — read at runtime by the ORM
)
from xtr_security_oauth2_server.value_object.redirect_uri import (
    RedirectUri as RedirectUriValue,  # noqa: TC001 — read at runtime by the ORM
)
from xtr_security_oauth2_server.value_object.scope import (
    Scope as ScopeValue,  # noqa: TC001 — read at runtime by the ORM
)

from ._tables import (
    ACTIVE_COLUMN,
    ALLOW_PLAIN_TEXT_PKCE_COLUMN,
    GRANTS_COLUMN,
    NAME_COLUMN,
    REDIRECT_URIS_COLUMN,
    SCOPES_COLUMN,
    SECRET_COLUMN,
)

__all__ = ["ClientMappingMixin"]


class ClientMappingMixin:
    """Declares a client's registration columns, and nothing about its table.

    What an application mixes into its own client class so the package's
    columns come along. It has no table and no identifier of its own on
    purpose: which column identifies a client is the application's to choose —
    the primary key on a base of its own, or a unique column beside an
    existing key on a base that already has one — and that choice is also what
    the credential tables point at.

    An application's class is then its own three parts: this mixin for the
    registration,
    :class:`~xtr_security_oauth2_server.model.abstract_client.AbstractClient`
    for the behaviour, and its declarative base for the mapping::

        class AppClient(ClientMappingMixin, AbstractClient, Base):
            __tablename__ = "app_client"

            _identifier = mapped_column("identifier", String(32), primary_key=True)
            tenant = mapped_column("tenant", String(32), nullable=True)

    Every column lands on the private attribute the model already keeps the
    value in, so a row read back is the model it was written from and no
    conversion sits in between. The constructor is the model's own and a load
    never runs it: a stored client comes back with what was stored, including
    the fields the constructor would have reset.

    Not used by the client this package ships, which is mapped from the
    driver along with the credentials it is pointed at. The columns are not
    merely alike but the same ones twice over: both sides build them from one
    description, each getting objects of its own, since a column belongs to a
    single table.
    """

    _name: Mapped[str] = NAME_COLUMN.for_class()
    _secret: Mapped[str | None] = SECRET_COLUMN.for_class()
    _redirect_uris: Mapped[Sequence[RedirectUriValue]] = REDIRECT_URIS_COLUMN.for_class()
    _grants: Mapped[Sequence[GrantValue]] = GRANTS_COLUMN.for_class()
    _scopes: Mapped[Sequence[ScopeValue]] = SCOPES_COLUMN.for_class()
    _active: Mapped[bool] = ACTIVE_COLUMN.for_class()
    _allow_plain_text_pkce: Mapped[bool] = ALLOW_PLAIN_TEXT_PKCE_COLUMN.for_class()
