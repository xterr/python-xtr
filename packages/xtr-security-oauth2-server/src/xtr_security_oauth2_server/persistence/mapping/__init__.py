"""The tables a stored deployment keeps its clients and credentials in, and the mapping.

One driver, built from the four settings that change what there is to store.
An application hands it to the ORM integration's mapping pass, which puts the
tables into the definitions of the connection it picked — so the application
generates its own revision from them, rather than running one shipped here.

An application owning its client class mixes
:class:`~xtr_security_oauth2_server.persistence.mapping.client_mapping_mixin.ClientMappingMixin`
into it for the registration columns, and the driver points the credentials at
whichever table the application mapped it to.
"""

from __future__ import annotations

from .client_mapping_mixin import ClientMappingMixin
from .driver import Driver
from .mapped_table import mapped_table

__all__ = ["ClientMappingMixin", "Driver", "mapped_table"]
