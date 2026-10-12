"""The credential revokers, which live beside the persistence that can run them.

Taking back everything a user or a client holds is one statement per table, not
a walk through a manager, so an implementation belongs where the tables are.
One so far: the stored one, for a deployment on a database.
"""

from __future__ import annotations

from .orm_credentials_revoker import OrmCredentialsRevoker

__all__ = ["OrmCredentialsRevoker"]
